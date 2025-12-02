#pragma once

#include "dpp/dpp.h"
#include "dpp/coro.h"

#include "Context.h"
#include "Core/Commands.h"

namespace iter8
{
	class Cog
	{
	public:
		Cog( Context& ctx )
			: ctx_{ ctx }
		{}

		void AddCommand( CommandDefinition const& command, SlashCommandHandler auto&& handler )
		{
			dpp::slashcommand cmd{
				command.name, command.description, ctx_.bot.me.id
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

			ctx_.bot.global_command_create( cmd );

			ctx_.bot.register_command( command.name, std::move( handler ) );
		}

		template < std::derived_from< dpp::event_dispatch_t > event_t >
		void AddListener( dpp::event_router_t< event_t >& event, ListenerHandler< event_t > auto&& handler )
		{
			event( handler );
		}

	protected:
		Context& ctx_;
	};

	template < typename T >
	concept IsCog = std::derived_from< T, Cog >;
} // namespace iter8