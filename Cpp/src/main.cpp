#include <dpp/dpp.h>
#include <cstdlib>


int main() {
    auto const env_token = std::getenv("BOT_TOKEN");
    if (env_token == nullptr) {
        std::printf("no token");
        return 1;
    }

    dpp::cluster bot(env_token);

    bot.on_slashcommand([](auto event) {
        std::printf("Command: {}", event.command.get_command_name());
        if (event.command.get_command_name() == "ping") {
            event.reply("Pong!");
        }
        });

    bot.on_ready([&bot](auto event) {
        if (dpp::run_once<struct register_bot_commands>()) {
            std::printf("run_once global sync");

            //bot.global_command_create(
            //    dpp::slashcommand("ping", "Ping pong!", bot.me.id)
            //);

            bot.global_commands_get([](dpp::confirmation_callback_t const& response) {

                if (response.is_error()) {
                    auto err = response.get_error();
                    return;
                }

                auto const& commands = std::get<dpp::slashcommand_map >(response.value);

                for (auto const& [command_id, command_info] : commands) {
                    auto a = 1; // Can inspect commands here
                }

                auto a = 1;
                });

            bot.guild_command_create(
                dpp::slashcommand("ping", "Ping pong!", bot.me.id),
                1439936989355970592
            );
        }
        });

    bot.start(dpp::st_wait);
    return 0;
}
