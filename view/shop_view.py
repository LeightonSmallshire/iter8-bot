import discord
from discord import app_commands
import discord.ui
from typing import Callable
import logging
import re
import utils.database as db_utils
import utils.log as log_utils
from utils.model import Purchase
import utils.shop as shop_utils
import traceback

_log = logging.getLogger(__name__)
_log.addHandler(logging.FileHandler('data/logs.log'))
_log.addHandler(log_utils.DatabaseHandler())


class ShopOptionsView(discord.ui.View):
    def __init__(self, item: type['shop_utils.ShopItem'], buyer_id: int):
        super().__init__(timeout=120)
        self.item = item
        self.buyer_id = buyer_id
        self.context: dict = {}

        # Collect components from handlers
        for comp in self.item.get_input_handlers():
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

            item = view.item

            # Example: consume view.context for final logic
            user = view.context.get("user")
            duration = view.context.get("duration")
            summary = []
            if user:
                summary.append(f"Target: <@{user}>")
            if duration:
                summary.append(f"Duration: {duration}m")
            desc = ", ".join(summary) or ""

            if await db_utils.can_afford_purchase(interaction.user.id, item.COST):
                count = duration if duration else 1
                db = await db_utils.Database(db_utils.DATABASE_NAME, defer_commit=True).connect()
                try:
                    await db.insert(Purchase(None, item.ITEM_ID, item.COST * count, interaction.user.id, item.AUTO_USE))
                    await view.item.handle_purchase(interaction, view.context)
                    await db.commit()

                    await interaction.edit_original_response(
                        view=None, content=f"✅ Purchased **{view.item.DESCRIPTION}** ({desc})."
                    )
                except BaseException as e:
                    await db.rollback()
                    await interaction.edit_original_response(
                        view=None, content=f"❌ Purchase failed to process."
                    )
                    traceback.print_exception(e)

            else:
                await interaction.edit_original_response(
                    view=None, content=f"❌ You can't afford this purchase."
                )


class ShopSelect(discord.ui.Select):
    def __init__(self):
        self.items = shop_utils.SHOP_ITEMS
        super().__init__(
            placeholder="Choose an item…",
            options=[discord.SelectOption(label=i.DESCRIPTION, value=str(i.ITEM_ID)) for i in self.items],
        )

    async def callback(self, interaction: discord.Interaction):
        item = next(i for i in self.items if str(i.ITEM_ID) == self.values[0])
        view = ShopOptionsView(item, interaction.user.id)
        await interaction.response.send_message(
            f"Configure your **{item.DESCRIPTION}** purchase:", view=view, ephemeral=True
        )


class ShopView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ShopSelect())
