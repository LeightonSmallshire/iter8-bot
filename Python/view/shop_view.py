from __future__ import annotations

import datetime
import logging
import traceback
from typing import Any, Dict, List, Type

import discord
import discord.ui

import utils.database as db_utils
import utils.log as log_utils
import utils.shop as shop_utils
from utils.model import Purchase

_log = logging.getLogger(__name__)
_log.addHandler(logging.FileHandler('data/logs.log', encoding='utf-8'))
_log.addHandler(log_utils.DatabaseHandler())


class ShopOptionsView(discord.ui.View):
    context: Dict[str, Any]

    def __init__(self, item: type[shop_utils.ShopItem], buyer_id: int):
        super().__init__(timeout=120)
        self.item = item
        self.buyer_id = buyer_id
        self.context: Dict[str, Any] = {}

        # Collect components from handlers
        for comp in self.item.get_input_handlers():
            self.add_item(comp)

        # Always add confirm button
        self.add_item(self.ConfirmButton())

    class ConfirmButton(discord.ui.Button[Any]):
        def __init__(self) -> None:
            super().__init__(label="Confirm Purchase", style=discord.ButtonStyle.green)

        async def callback(self, interaction: discord.Interaction) -> None:
            view = self.view
            if not isinstance(view, ShopOptionsView):
                await interaction.response.send_message(
                    "Unexpected view type.", ephemeral=True
                )
                return
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

            _log.info(f"{interaction.user.name} purchased {item.DESCRIPTION}: ({desc})")

            sale, _ = await shop_utils.is_ongoing_sale()
            discount = 0.5 if sale else 1
            
            count = int(duration) if duration else 1
            item_cost = int(item.COST * discount) if item.ITEM_ID != shop_utils.BlackFridaySaleItem.ITEM_ID else item.COST
            
            cost = item_cost * count

            if await shop_utils.can_afford_purchase(interaction.user.id, int(cost)):
                db = await db_utils.Database(db_utils.DATABASE_NAME, defer_commit=True).connect()
                try:
                    await db.insert(Purchase(0, datetime.datetime.now(), item.ITEM_ID, int(cost), interaction.user.id, item.AUTO_USE))
                    await view.item.handle_purchase(interaction, view.context)
                    await db.commit()

                    await interaction.edit_original_response(
                        view=None, content=f"✅ Purchased **{view.item.DESCRIPTION}** ({desc})."
                    )
                except BaseException as e:
                    await db.rollback()
                    await interaction.edit_original_response(
                        view=None, content=f"❌ Purchase failed to process ({str(e)})."
                    )
                    traceback.print_exception(e)

            else:
                await interaction.edit_original_response(
                    view=None, content="❌ You can't afford this purchase."
                )


class ShopSelect(discord.ui.Select[discord.ui.View]):
    items: List[type[shop_utils.ShopItem]]

    def __init__(self) -> None:
        self.items = shop_utils.SHOP_ITEMS
        super().__init__(
            placeholder="Choose an item…",
            options=[discord.SelectOption(label=i.DESCRIPTION, value=str(i.ITEM_ID)) for i in self.items],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        item = next(i for i in self.items if str(i.ITEM_ID) == self.values[0])
        view = ShopOptionsView(item, interaction.user.id)
        await interaction.response.send_message(
            f"Configure your **{item.DESCRIPTION}** purchase:", view=view, ephemeral=True
        )


class ShopView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)
        self.add_item(ShopSelect())
