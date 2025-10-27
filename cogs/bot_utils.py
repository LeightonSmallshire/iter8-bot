class Guilds:
    Paradise = 1416007094339113071
    Innov8 = 1325821294427766784
    Innov8_DevOps = 1425873966035238975

class Users:
    Nathan = 1326156803108503566
    Leighton = 1416017385596653649
    Charlotte = 1401855871633330349
    Ed = 1356197937520181339
    Matt = 1333425159729840188
    Tom = 1339198017324187681

def is_guild_paradise(ctx):
    return ctx.guild and ctx.guild.id == Guilds.Paradise


class Channels:
    ParadiseBotBrokenSpam = 1427971106920202240