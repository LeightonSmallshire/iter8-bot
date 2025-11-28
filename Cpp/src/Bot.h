#pragma once

#include "dpp/dpp.h"

#include "Cogs/Cog.h"

namespace iter8
{
	class DiscordBot
	{
	public:
		DiscordBot();

		template < IsCog T >
		void RegisterCog()
		{
			auto cog = std::make_unique< T >( bot_ );
			cogs_.push_back( std::move( cog ) );
		}

	private:
		dpp::cluster bot_{};
		std::vector< std::unique_ptr< Cog > > cogs_;
	};
} // namespace iter8