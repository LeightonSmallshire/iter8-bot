#pragma once

#include "dpp/dpp.h"
#include "dpp/coro.h"

#include "Core/Commands.h"

namespace iter8
{
	class Cog
	{
	public:
		Cog( dpp::cluster& bot )
			: bot_{ bot }
		{}

		void AddCommand( CommandDefinition const& command, SlashCommandHandler auto&& handler )
		{
			dpp::slashcommand cmd{
				command.name, command.description, bot_.me.id
			};

			for ( auto const& param : command.parameters )
			{
				auto arg = dpp::command_option{
					param.type,
					param.name,
					param.description,
					param.required
				};
				cmd.add_option( arg );
			}

			bot_.global_command_create( cmd );

			bot_.register_command( command.name, std::move( handler ) );
		}

		template < std::derived_from< dpp::event_dispatch_t > event_t >
		void AddListener( dpp::event_router_t< event_t >& event, ListenerHandler< event_t > auto&& handler )
		{
			event( handler );
		}

	protected:
		dpp::cluster& bot_;
	};

	template < typename T >
	concept IsCog = std::derived_from< T, Cog >;
} // namespace iter8