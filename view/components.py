import discord
import discord.ui
import re


class UserSelect(discord.ui.UserSelect):
    def __init__(self):
        super().__init__(placeholder="Select a user to target")

    async def callback(self, interaction: discord.Interaction):
        context = self.view.context
        context["user"] = self.values[0].id
        await interaction.response.defer()

        
class DurationSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=f"{m} minute(s)", value=str(m))
            for m in [1, 2, 5, 10, 15, 30, 60]
        ]
        super().__init__(placeholder="Choose duration", options=options)

    async def callback(self, interaction: discord.Interaction):
        context = self.view.context
        context["duration"] = int(self.values[0])
        await interaction.response.defer()


class ColourSelect(discord.ui.Button):       
    def __init__(self):
        super().__init__(label="Enter colour hex", style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction):
        class ColourModal(discord.ui.Modal):
            HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}){1,2}$")

            def __init__(self, view):
                self.view = view
                self.colour_input = discord.ui.TextInput(label="HEX code", placeholder="#ff8800")
                super().__init__(title="Enter a colour hex code")

            async def on_submit(self, interaction: discord.Interaction):
                val = self.colour_input.value.strip()
                if not self.HEX_RE.fullmatch(val):
                    await interaction.response.send_message(
                        "Invalid colour code. Use format like `#RRGGBB`.",
                        ephemeral=True
                    )
                    return
                self.view.context["colour"] = self.colour_input.value
                await interaction.response.defer()

        await interaction.response.send_modal(ColourModal(self.view))


class TextSelect(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Enter text", style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction):
        class TextModal(discord.ui.Modal):
            def __init__(self, view):
                self.view = view
                self.text_input = discord.ui.TextInput(label="Your text", placeholder="Type here...")
                super().__init__(title="Enter your text...")

            async def on_submit(self, interaction: discord.Interaction):
                self.view.context["text"] = self.text_input.value
                await interaction.response.defer()
        await interaction.response.send_modal(TextModal(self.view))