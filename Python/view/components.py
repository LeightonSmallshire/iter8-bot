import discord
import discord.ui
import re
from io import BytesIO
from PIL import Image
from typing import Any


class UserSelect(discord.ui.UserSelect[discord.ui.View]):
    def __init__(self) -> None:
        super().__init__(placeholder="Select a user to target")

    async def callback(self, interaction: discord.Interaction) -> None:
        user = self.values[0]
        guild = interaction.guild
        if guild is None:
            return
        view = self.view
        if view is None:
            return
        if user.bot or user.id == guild.owner_id or user.id == interaction.user.id:
            await interaction.response.send_message("Invalid selection.", ephemeral=True)
            return

        context: dict[str, Any] = view.context  # type: ignore[attr-defined]
        context["user"] = self.values[0].id
        await interaction.response.defer()


class DurationSelect(discord.ui.Select[discord.ui.View]):
    def __init__(self) -> None:
        options = [
            discord.SelectOption(label=f"{m} minute(s)", value=str(m))
            for m in [1, 2, 5, 10, 15, 30, 60]
        ]
        super().__init__(placeholder="Choose duration", options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if view is None:
            return
        context: dict[str, Any] = view.context  # type: ignore[attr-defined]
        context["duration"] = int(self.values[0])
        await interaction.response.defer()


class ColourSelect(discord.ui.Button[Any]):
    def __init__(self) -> None:
        super().__init__(label="Enter colour", style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction) -> None:
        class ColourModal(discord.ui.Modal):
            HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}){1,2}$")

            def __init__(self, parent: ColourSelect) -> None:
                self.parent = parent
                super().__init__(title="Enter a colour hex code")
                self.colour_input: discord.ui.TextInput[discord.ui.View] = discord.ui.TextInput(label="HEX code", placeholder="#ff8800")
                self.add_item(self.colour_input)

            async def make_color_emoji(self, guild: discord.Guild, hex_code: str) -> discord.Emoji:
                rgb = tuple(int(hex_code[i:i+2], 16) for i in (1, 3, 5))
                im = Image.new("RGB", (128, 128), rgb)

                buf = BytesIO()
                im.save(buf, "PNG")
                buf.seek(0)

                image = buf.read()

                return await guild.create_custom_emoji(name=f"col_{hex_code.lstrip('#')}", image=image)

            async def on_submit(self, interaction: discord.Interaction) -> None:
                guild = interaction.guild
                if guild is None:
                    return
                val = self.colour_input.value.strip()
                if not self.HEX_RE.fullmatch(val):
                    await interaction.response.send_message(
                        "Invalid colour code. Use format like `#RRGGBB`.",
                        ephemeral=True
                    )
                    return
                parent_view: Any = self.parent.view
                parent_view.context["colour"] = self.colour_input.value

                emoji = await self.make_color_emoji(guild, self.colour_input.value)

                self.parent.label = self.colour_input.value
                self.parent.emoji = emoji

                await interaction.response.edit_message(view=self.parent.view)
                await guild.delete_emoji(emoji)

        await interaction.response.send_modal(ColourModal(self))


class TextSelect(discord.ui.Button[Any]):
    def __init__(self, title: str, label: str, placeholder: str) -> None:
        self.title = title
        self.edit_label = label
        self.placeholder = placeholder
        super().__init__(label=title, style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction) -> None:
        class TextModal(discord.ui.Modal):
            def __init__(self, select: TextSelect) -> None:
                self.parent = select
                super().__init__(title=select.title)
                self.text_input: discord.ui.TextInput[discord.ui.View] = discord.ui.TextInput(label=select.label, placeholder=select.placeholder)
                self.add_item(self.text_input)

            async def on_submit(self, interaction: discord.Interaction) -> None:
                parent_view: Any = self.parent.view
                parent_view.context["text"] = self.text_input.value
                self.parent.label = self.text_input.value
                await interaction.response.edit_message(view=self.parent.view)
        await interaction.response.send_modal(TextModal(self))
