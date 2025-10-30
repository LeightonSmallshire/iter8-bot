import discord
from discord import app_commands
import datetime
import utils.database as db_utils

class PurchaseButton(discord.ui.View):
    def __init__(self, item, user_id):
        super().__init__(timeout=60)
        self.item = item
        self.user_id = user_id

    @discord.ui.button(label="Confirm Purchase", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("You can’t use another user’s purchase panel.", ephemeral=True)
            return

        await interaction.response.defer(thinking=True, ephemeral=True)
        # Replace with your DB call
        ok, reason = await db_utils.purchase(interaction.user.id, self.item.id)
        if ok:
            await interaction.followup.send(
                f"✅ You bought **{self.item.description}** for {datetime.timedelta(seconds=self.item.cost)}.",
                ephemeral=True
            )
        else:
            await interaction.followup.send(f"❌ Purchase failed: {reason}", ephemeral=True)


class ShopSelect(discord.ui.Select):
    def __init__(self, items):
        options = [
            discord.SelectOption(
                label=item.description[:100],
                description=f"Cost: {datetime.timedelta(seconds=item.cost)}",
                value=str(item.id)
            )
            for item in items[:25]
        ]
        super().__init__(placeholder="Browse shop items...", options=options)

        self.items_list = items

    async def callback(self, interaction: discord.Interaction):
        item_id = int(self.values[0])
        item = next(i for i in self.items_list if i.id == item_id)
        # Each user sees their own ephemeral confirmation
        view = PurchaseButton(item, interaction.user.id)
        await interaction.response.send_message(
            f"You selected **{item.description}** for {datetime.timedelta(seconds=item.cost)}.",
            view=view,
            ephemeral=True
        )


class ShopView(discord.ui.View):
    def __init__(self, items):
        super().__init__(timeout=None)
        self.add_item(ShopSelect(items))