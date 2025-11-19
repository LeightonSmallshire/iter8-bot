#include <dpp/dpp.h>
#include <cstdlib>

int main() {
    auto const env_token = std::getenv("BOT_TOKEN");
    if (env_token == nullptr) {

    }

    dpp::cluster bot(env_token);

    bot.on_slashcommand([](auto event) {
        if (event.command.get_command_name() == "ping") {
            event.reply("Pong!");
        }
    });

    bot.on_ready([&bot](auto event) {
        if (dpp::run_once<struct register_bot_commands>()) {
            bot.global_command_create(
                dpp::slashcommand("ping", "Ping pong!", bot.me.id)
            );
        }
    });

    bot.start(dpp::st_wait);
    return 0;
}
