import asyncio
import json
import time
from collections.abc import Coroutine
from pathlib import Path
from typing import Any

import discord
import logfire
from discord.ext import commands, tasks

import utils.allowlist as allowlist
import utils.bot as bot_utils

ROLE_CHANNELS: dict[str, list[str]] = {
    "Shitposter": ["Text Channels"],
    "Worker": ["Non-Shitposts", "Stonks"],
    "Susposter": ["channels to kill?", "No One See This"],
    "Crafter": ["bots", "Happy Room"],
    "NSFW": [],
}

NSFW_ROLE = "NSFW"
WELCOME_NAME = "welcome"
TAUNT_CHANNEL_NAME = "general-idiocy"
TAUNT_COOLDOWN_SECONDS = 600.0
STATE_FILE = Path("data/welcome_state.json")

REASON = "welcome cog reconcile"

PICK_CUSTOM_ID = "wrole:pick"
MODAL_CUSTOM_ID = "wrole:picker"
GROUP_CUSTOM_ID = "wrole:roles"


def _load_state() -> dict[str, Any]:
    try:
        if STATE_FILE.is_file():
            data: Any = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except (OSError, json.JSONDecodeError) as e:
        logfire.warning("welcome_state_load_failed", error=str(e))
    return {"roles": {}, "channel": 0, "message": 0}


def _save_state(state: dict[str, Any]) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except OSError as e:
        logfire.warning("welcome_state_save_failed", error=str(e))


def _resolve_gate_roles(guild: discord.Guild) -> dict[str, discord.Role] | None:
    found = {name: discord.utils.get(guild.roles, name=name) for name in ROLE_CHANNELS}
    if any(role is None for role in found.values()):
        return None
    return {name: role for name, role in found.items() if role is not None}


def _role_diff(current: set[str], selected: set[str]) -> tuple[list[str], list[str]]:
    to_add = [name for name in ROLE_CHANNELS if name in selected and name not in current]
    to_remove = [name for name in ROLE_CHANNELS if name in current and name not in selected]
    return to_add, to_remove


def _option_description(name: str) -> str:
    categories = ROLE_CHANNELS[name]
    if not categories:
        return "Nothing. You just wanted to see nsfw."
    return f"Unlocks: {', '.join(categories)}"[:100]


class PickRolesButton(discord.ui.Button[discord.ui.View]):
    def __init__(self) -> None:
        super().__init__(
            label="Pick your roles", style=discord.ButtonStyle.primary, custom_id=PICK_CUSTOM_ID
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if not await allowlist.deny_if_not_allowed(interaction):
            return
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Only works in a server.", ephemeral=True)
            return
        if _resolve_gate_roles(guild) is None:
            await interaction.response.send_message(
                "The roles aren't set up yet — try again in a minute.", ephemeral=True
            )
            return
        if isinstance(interaction.user, discord.Member):
            member = interaction.user
        else:
            member = await guild.fetch_member(interaction.user.id)
        held = {role.name for role in member.roles}
        await interaction.response.send_modal(RolePickerModal(held))


class RolePickerModal(discord.ui.Modal):
    def __init__(self, held: set[str]) -> None:
        super().__init__(title="Pick your roles", timeout=None, custom_id=MODAL_CUSTOM_ID)
        self._client: discord.Client | None = None
        options = [
            discord.CheckboxGroupOption(
                label=name,
                value=name,
                default=name in held,
                description=_option_description(name),
            )
            for name in ROLE_CHANNELS
        ]
        self.group: discord.ui.CheckboxGroup[discord.ui.View] = discord.ui.CheckboxGroup(
            custom_id=GROUP_CUSTOM_ID,
            options=options,
            min_values=0,
            max_values=len(ROLE_CHANNELS),
            required=False,
        )
        self.add_item(
            discord.ui.Label(
                text="Your roles",
                description="Tick to join, untick to leave.",
                component=self.group,
            )
        )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        self._client = interaction.client
        if not await allowlist.deny_if_not_allowed(interaction):
            return
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Only works in a server.", ephemeral=True)
            return
        roles = _resolve_gate_roles(guild)
        if roles is None:
            await interaction.response.send_message(
                "The roles aren't set up yet — try again in a minute.", ephemeral=True
            )
            return
        if isinstance(interaction.user, discord.Member):
            member = interaction.user
        else:
            member = await guild.fetch_member(interaction.user.id)

        current = {role.name for role in member.roles}
        to_add, to_remove = _role_diff(current, set(self.group.values))
        try:
            if to_add:
                await member.add_roles(*(roles[name] for name in to_add), reason=REASON)
            if to_remove:
                await member.remove_roles(*(roles[name] for name in to_remove), reason=REASON)
        except discord.Forbidden:
            await interaction.response.send_message(
                "I can't change that role — it is above my highest role.", ephemeral=True
            )
            return
        except discord.HTTPException as e:
            logfire.warning("role_sync_failed", error=str(e))
            if not interaction.response.is_done():
                await interaction.response.send_message("Something went wrong.", ephemeral=True)
            return

        parts: list[str] = []
        if to_add:
            parts.append("Added " + ", ".join(f"**{name}**" for name in to_add) + ".")
        if to_remove:
            parts.append("Removed " + ", ".join(f"**{name}**" for name in to_remove) + ".")
        summary = " ".join(parts) if parts else "Your roles are unchanged."
        await interaction.response.send_message(summary, ephemeral=True)

    def stop(self) -> None:
        super().stop()
        if self._client is not None:
            self._client.add_view(RolePickerModal(set()))


class WelcomeView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)
        self.add_item(PickRolesButton())


class WelcomeCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot_: commands.Bot = bot
        self._lock = asyncio.Lock()
        self._state: dict[str, Any] = _load_state()
        self._sending_welcome = False
        self._taunt_times: dict[int, float] = {}
        logfire.info(f"Cog '{self.qualified_name}' initialized.")

    async def cog_load(self) -> None:
        self.bot_.add_view(WelcomeView())
        self.bot_.add_view(RolePickerModal(set()))
        self.sweep.start()
        self._spawn(self.reconcile_all())

    async def cog_unload(self) -> None:
        self.sweep.cancel()

    def _spawn(self, coro: Coroutine[Any, Any, None]) -> None:
        task = asyncio.create_task(coro)
        task.add_done_callback(self._task_done)

    @staticmethod
    def _task_done(task: asyncio.Task[None]) -> None:
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logfire.error("welcome_task_failed", error=str(exc))

    @tasks.loop(minutes=10)
    async def sweep(self) -> None:
        try:
            await self.reconcile_all()
        except Exception as e:
            logfire.error("welcome_sweep_failed", error=str(e))

    @sweep.before_loop
    async def before_sweep(self) -> None:
        await self.bot_.wait_until_ready()

    def _guild(self) -> discord.Guild | None:
        return discord.utils.get(self.bot_.guilds, id=bot_utils.Guilds.Default)

    def _set(self, key: str, value: Any) -> None:
        if self._state.get(key) == value:
            return
        self._state[key] = value
        _save_state(self._state)

    async def reconcile_all(self) -> None:
        async with self._lock:
            guild = self._guild()
            if guild is None:
                return
            try:
                await self._reconcile_roles(guild)
                welcome = await self._ensure_welcome_channel(guild)
                await self._reconcile_channels(guild, welcome)
                await self._reconcile_system_channel(guild, welcome)
                await self._reconcile_message(guild, welcome)
            except discord.HTTPException as e:
                logfire.error("welcome_reconcile_failed", error=str(e))

    async def _reconcile_roles(self, guild: discord.Guild) -> None:
        roles_state: dict[str, Any] = self._state.setdefault("roles", {})
        if not isinstance(roles_state, dict):
            roles_state = {}
            self._state["roles"] = roles_state
        changed = False

        for name in ROLE_CHANNELS:
            role: discord.Role | None = None
            saved_id = roles_state.get(name)
            if isinstance(saved_id, int):
                role = guild.get_role(saved_id)
            if role is None:
                role = discord.utils.get(guild.roles, name=name)
            if role is None:
                try:
                    role = await guild.create_role(
                        name=name, permissions=discord.Permissions.none(), reason=REASON
                    )
                    logfire.info("welcome_role_created", role=name, role_id=role.id)
                except discord.HTTPException as e:
                    logfire.error("welcome_role_create_failed", role=name, error=str(e))
                    continue

            expected_perms = discord.Permissions.none()
            kwargs: dict[str, Any] = {}
            if role.name != name:
                kwargs["name"] = name
            if role.permissions.value != expected_perms.value:
                kwargs["permissions"] = expected_perms
            if role.mentionable:
                kwargs["mentionable"] = False
            if role.hoist:
                kwargs["hoist"] = False
            if kwargs:
                try:
                    edited = await role.edit(reason=REASON, **kwargs)
                    if edited is not None:
                        role = edited
                    logfire.info("welcome_role_restored", role=name, changed=list(kwargs))
                except discord.Forbidden:
                    logfire.warning("welcome_role_edit_forbidden", role=name)
                    continue
                except discord.HTTPException as e:
                    logfire.error("welcome_role_edit_failed", role=name, error=str(e))
                    continue

            if roles_state.get(name) != role.id:
                roles_state[name] = role.id
                changed = True

        if changed:
            _save_state(self._state)

    async def _ensure_welcome_channel(self, guild: discord.Guild) -> discord.TextChannel:
        channel = discord.utils.get(guild.text_channels, name=WELCOME_NAME)
        if channel is None:
            try:
                channel = await guild.create_text_channel(
                    WELCOME_NAME, overwrites=self._welcome_overwrites(guild), reason=REASON
                )
                logfire.info("welcome_channel_created", channel_id=channel.id)
            except discord.HTTPException as e:
                logfire.error("welcome_channel_create_failed", error=str(e))
                placeholder = discord.utils.get(guild.text_channels, name=WELCOME_NAME)
                if placeholder is None:
                    raise
                channel = placeholder
        self._set("channel", channel.id)
        return channel

    async def _reconcile_channels(self, guild: discord.Guild, welcome: discord.TextChannel) -> None:
        bot_role = guild.me.top_role if guild.me is not None else None
        allowed_roles = self._resolve_roles(guild)

        for channel in guild.channels:
            if channel.id == welcome.id:
                desired = self._welcome_overwrites(guild)
            else:
                desired = self._hidden_overwrites(guild, channel, bot_role, allowed_roles)

            if channel.overwrites == desired:
                continue
            try:
                await channel.edit(overwrites=desired, reason=REASON)
            except discord.Forbidden:
                logfire.warning("welcome_channel_edit_forbidden", channel=channel.name)
            except discord.HTTPException as e:
                logfire.error("welcome_channel_edit_failed", channel=channel.name, error=str(e))

    async def _reconcile_system_channel(self, guild: discord.Guild, welcome: discord.TextChannel) -> None:
        flags = guild.system_channel_flags
        channel_ok = guild.system_channel is not None and guild.system_channel.id == welcome.id
        if channel_ok and not flags.join_notification_replies:
            return
        me = guild.me
        if me is None or not me.guild_permissions.manage_guild:
            logfire.warning("welcome_system_channel_no_perm", guild_id=guild.id)
            return
        flags.join_notification_replies = False
        try:
            await guild.edit(system_channel=welcome, system_channel_flags=flags, reason=REASON)
            logfire.info("welcome_system_channel_set", channel_id=welcome.id)
        except discord.Forbidden:
            logfire.warning("welcome_system_channel_forbidden", guild_id=guild.id)
        except discord.HTTPException as e:
            logfire.error("welcome_system_channel_failed", error=str(e))

    @staticmethod
    def _resolve_roles(guild: discord.Guild) -> dict[discord.Role, list[str]]:
        resolved: dict[discord.Role, list[str]] = {}
        for name, category_names in ROLE_CHANNELS.items():
            if not category_names:
                continue
            role = discord.utils.get(guild.roles, name=name)
            if role is not None:
                resolved[role] = category_names
        return resolved

    @staticmethod
    def _merge_ow(current: discord.PermissionOverwrite, **changes: bool) -> discord.PermissionOverwrite:
        data: dict[str, Any] = dict(current)
        data.update(changes)
        return discord.PermissionOverwrite(**data)

    def _welcome_overwrites(self, guild: discord.Guild) -> dict[Any, discord.PermissionOverwrite]:
        everyone = guild.default_role
        desired: dict[Any, discord.PermissionOverwrite] = {
            everyone: discord.PermissionOverwrite(
                view_channel=True,
                read_message_history=True,
                send_messages=False,
                send_messages_in_threads=False,
                create_public_threads=False,
                create_private_threads=False,
            ),
        }
        if guild.me is not None:
            desired[guild.me] = discord.PermissionOverwrite(
                view_channel=True,
                read_message_history=True,
                send_messages=True,
                manage_messages=True,
            )
        return desired

    def _hidden_overwrites(
        self,
        guild: discord.Guild,
        channel: discord.abc.GuildChannel,
        bot_role: discord.Role | None,
        allowed_roles: dict[discord.Role, list[str]],
    ) -> dict[Any, discord.PermissionOverwrite]:
        desired = dict(channel.overwrites)
        everyone = guild.default_role
        desired[everyone] = self._merge_ow(
            desired.get(everyone, discord.PermissionOverwrite()),
            view_channel=False,
        )

        if bot_role is not None:
            desired[bot_role] = self._merge_ow(
                desired.get(bot_role, discord.PermissionOverwrite()),
                view_channel=True,
                send_messages=True,
                read_message_history=True,
            )

        for role, category_names in allowed_roles.items():
            if not self._channel_in_categories(channel, category_names):
                continue
            desired[role] = self._merge_ow(
                desired.get(role, discord.PermissionOverwrite()),
                view_channel=True,
                read_message_history=True,
                send_messages=True,
            )
        return desired

    @staticmethod
    def _channel_in_categories(channel: discord.abc.GuildChannel, category_names: list[str]) -> bool:
        if isinstance(channel, discord.CategoryChannel):
            return channel.name in category_names
        category = getattr(channel, "category", None)
        return category is not None and category.name in category_names

    async def _reconcile_message(self, guild: discord.Guild, welcome: discord.TextChannel) -> None:
        expected = self._build_embed(guild)
        message = await self._find_welcome_message(welcome)

        if message is None:
            await self._post_welcome(welcome, guild)
            return

        await self._delete_stray_own_messages(welcome, keep_id=message.id)

        components = sum(len(getattr(row, "children", [])) for row in message.components)
        embeds_ok = len(message.embeds) == 1 and message.embeds[0].to_dict() == expected.to_dict()
        if not embeds_ok or components != 1:
            try:
                await message.edit(embed=expected, view=WelcomeView())
                logfire.info("welcome_message_updated", message_id=message.id)
            except discord.HTTPException as e:
                logfire.error("welcome_message_edit_failed", error=str(e))
        if message.id != self._state.get("message"):
            self._set("message", message.id)

    async def _find_welcome_message(self, welcome: discord.TextChannel) -> discord.Message | None:
        state_id = self._state.get("message")
        if isinstance(state_id, int) and state_id:
            try:
                return await welcome.fetch_message(state_id)
            except discord.NotFound:
                pass
            except discord.HTTPException as e:
                logfire.warning("welcome_message_fetch_failed", error=str(e))
        async for msg in welcome.history(limit=20):
            if self.bot_.user is not None and msg.author.id == self.bot_.user.id:
                return msg
        return None

    async def _delete_stray_own_messages(self, welcome: discord.TextChannel, keep_id: int) -> None:
        if self.bot_.user is None:
            return
        async for msg in welcome.history(limit=20):
            if msg.author.id != self.bot_.user.id or msg.id == keep_id:
                continue
            try:
                await msg.delete()
                logfire.info("welcome_stray_removed", message_id=msg.id)
            except discord.HTTPException as e:
                logfire.warning("welcome_stray_delete_failed", error=str(e))

    async def _post_welcome(self, welcome: discord.TextChannel, guild: discord.Guild) -> None:
        self._sending_welcome = True
        try:
            message = await welcome.send(embed=self._build_embed(guild), view=WelcomeView())
            self._set("message", message.id)
            logfire.info("welcome_message_posted", message_id=message.id)
        except discord.HTTPException as e:
            logfire.error("welcome_message_post_failed", error=str(e))
        finally:
            self._sending_welcome = False

    @staticmethod
    def _build_embed(guild: discord.Guild) -> discord.Embed:
        embed = discord.Embed(
            title=f"Welcome to {guild.name}",
            color=discord.Color.blue(),
        )
        embed.description = (
            "This is the only channel you can see until you pick roles.\n"
            "Use the button below to pick your roles:"
        )
        for role_name, category_names in ROLE_CHANNELS.items():
            if category_names:
                lines: list[str] = []
                for category_name in category_names:
                    lines.extend(WelcomeCog._category_channels(guild, category_name))
                value = "\n".join(lines) if lines else "Nothing."
            else:
                value = "Nothing. You just wanted to see nsfw."
            embed.add_field(name=role_name, value=value[:1024], inline=False)
        embed.set_footer(text="Your choices apply as soon as you submit.")
        return embed

    @staticmethod
    def _category_channels(guild: discord.Guild, category_name: str) -> list[str]:
        category = discord.utils.get(guild.categories, name=category_name)
        if category is None:
            return [f"#{category_name}"]
        out: list[str] = []
        for channel in guild.channels:
            if getattr(channel, "category", None) is not category:
                continue
            if isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
                out.append(f"{channel.name} (voice)")
            elif isinstance(channel, (discord.ForumChannel, discord.TextChannel)):
                out.append(f"#{channel.name}")
            else:
                out.append(channel.name)
        return out

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.guild is None or message.guild.id != bot_utils.Guilds.Default:
            return
        if message.channel.id != self._state.get("channel"):
            return
        if message.author == self.bot_.user:
            if self._sending_welcome:
                self._set("message", message.id)
            return
        if message.type != discord.MessageType.default:
            return
        try:
            await message.delete()
        except discord.HTTPException as e:
            logfire.warning("welcome_stray_delete_failed", error=str(e))

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent) -> None:
        if payload.guild_id != bot_utils.Guilds.Default:
            return
        if payload.message_id != self._state.get("message"):
            return
        self._spawn(self.reconcile_all())

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        if after.guild.id != bot_utils.Guilds.Default:
            return
        nsfw = discord.utils.get(after.guild.roles, name=NSFW_ROLE)
        if nsfw is None or after.bot:
            return
        if nsfw not in after.roles or nsfw in before.roles:
            return

        now = time.monotonic()
        if now - self._taunt_times.get(after.id, 0.0) < TAUNT_COOLDOWN_SECONDS:
            return
        self._taunt_times[after.id] = now

        channel = discord.utils.get(after.guild.text_channels, name=TAUNT_CHANNEL_NAME)
        if channel is None:
            logfire.warning("nsfw_taunt_channel_missing", guild=after.guild.name)
            return
        try:
            await channel.send(
                f"@everyone {after.mention} wanted to see nsfw! Point and laugh!",
                allowed_mentions=discord.AllowedMentions(everyone=True, users=True, roles=False),
            )
        except discord.HTTPException as e:
            logfire.warning("nsfw_taunt_failed", error=str(e))

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel) -> None:
        if channel.guild.id == bot_utils.Guilds.Default:
            self._spawn(self.reconcile_all())

    @commands.Cog.listener()
    async def on_guild_channel_update(
        self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel
    ) -> None:
        if after.guild.id == bot_utils.Guilds.Default:
            self._spawn(self.reconcile_all())

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel) -> None:
        if channel.guild.id == bot_utils.Guilds.Default:
            self._spawn(self.reconcile_all())

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role) -> None:
        if role.guild.id == bot_utils.Guilds.Default:
            self._spawn(self.reconcile_all())

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role) -> None:
        if after.guild.id == bot_utils.Guilds.Default:
            self._spawn(self.reconcile_all())

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role) -> None:
        if role.guild.id == bot_utils.Guilds.Default:
            self._spawn(self.reconcile_all())


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WelcomeCog(bot))
