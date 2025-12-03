#pragma once

#include "dpp/dpp.h"

#include "Context.h"
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
			auto cog = std::make_unique< T >( ctx_ );
			cogs_.push_back( std::move( cog ) );
		}

	private:
		void Init();
		void InitDB();
		void InitLog();
		void InitBot();

		dpp::task<void> OnReady( dpp::ready_t const& e );

	private:
		Context ctx_;
		std::vector< std::unique_ptr< Cog > > cogs_;
	};
} // namespace iter8