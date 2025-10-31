import discord
from discord import app_commands
import discord.ui
from typing import Callable
import datetime
import utils.database as db_utils
import utils.shop as shop_utils
from utils.model import ShopItem, PurchaseHandler

SHOP_HANDLER_FUNCS: dict[str, Callable] = {}

def register_shop_builder(name: str):
    """Decorator to register a handler function by name."""
    def decorator(func):
        SHOP_HANDLER_FUNCS[name] = func
        return func
    return decorator

@register_shop_builder("UserChoice")
def build_user_choice(item: ShopItem, buyer_id: int):
    class UserSelect(discord.ui.UserSelect):
        def __init__(self):
            super().__init__(placeholder="Select a user to target")

        async def callback(self, interaction: discord.Interaction):
            context = self.view.context
            context["user"] = self.values[0].id
            await interaction.response.defer()

    return [UserSelect()]

@register_shop_builder("DurationChoice")
def build_duration_choice(item: ShopItem, buyer_id: int):
    class DurationSelect(discord.ui.Select):
        def __init__(self):
            options = [
                discord.SelectOption(label=f"{m} minute(s)", value=str(m))
                for m in [1, 2, 5, 10, 15, 30, 60]
            ]
            super().__init__(placeholder="Choose duration", options=options)

        async def callback(self, interaction: discord.Interaction):
            self.view.context["duration"] = int(self.values[0])
            await interaction.response.defer()

    return [DurationSelect()]

class ShopOptionsView(discord.ui.View):
    def __init__(self, item: ShopItem, buyer_id: int, handler_keys: list[str]):
        super().__init__(timeout=120)
        self.item = item
        self.buyer_id = buyer_id
        self.context: dict = {}

        # Collect components from handlers
        for key in handler_keys:
            builder = SHOP_HANDLER_FUNCS.get(key)
            if not builder:
                continue
            components = builder(item, buyer_id)
            for comp in components:
                self.add_item(comp)

        # Always add confirm button
        self.add_item(self.ConfirmButton())

    class ConfirmButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="Confirm Purchase", style=discord.ButtonStyle.green)

        async def callback(self, interaction: discord.Interaction):
            view: ShopOptionsView = self.view
            if interaction.user.id != view.buyer_id:
                await interaction.response.send_message(
                    "You can’t confirm someone else’s purchase.", ephemeral=True
                )
                return

            await interaction.response.edit_message(view=None, content="Processing purchase…")

            cost = view.item.cost

            # Example: consume view.context for final logic
            user = view.context.get("user")
            duration = view.context.get("duration")
            summary = []
            if user:
                summary.append(f"Target: <@{user}>")
            if duration:
                cost *= duration
                summary.append(f"Duration: {duration}m")
            desc = ", ".join(summary) or ""

            if await db_utils.can_afford_purchase(interaction.user.id, cost):
                count = duration if duration else 1
                await db_utils.purchase(interaction.user.id, view.item, count)
                await shop_utils.do_purchase(interaction, view.item, view.context)

                await interaction.edit_original_response(
                    view=None, content=f"✅ Purchased **{view.item.description}** ({desc})."
                )
            else:
                await interaction.edit_original_response(
                    view=None, content=f"❌ You can't afford this purchase."
                )



class ShopSelect(discord.ui.Select):
    def __init__(self, items: list[ShopItem]):
        super().__init__(
            placeholder="Choose an item…",
            options=[discord.SelectOption(label=i.description, value=str(i.id)) for i in items],
        )
        self.items = items

    async def callback(self, interaction: discord.Interaction):
        item = next(i for i in self.items if str(i.id) == self.values[0])
        handlers = await db_utils.get_handlers(item.id)

        view = ShopOptionsView(item, interaction.user.id, handlers)
        await interaction.response.send_message(
            f"Configure your **{item.description}** purchase:", view=view, ephemeral=True
        )


class ShopView(discord.ui.View):
    def __init__(self, items):
        super().__init__(timeout=None)
        self.add_item(ShopSelect(items))