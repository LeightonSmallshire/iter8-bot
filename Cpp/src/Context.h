#pragma once

#include "Core/Discord.h"
#include "Database/Connection.h"

#include "dpp/dpp.h"

namespace iter8
{
	struct Context
	{
		dpp::cluster bot;
		db::Connection db;

		std::map< std::string, std::map< std::string, AutocompleteHandler > > autocomplete_handlers;
		std::map< dpp::snowflake, std::optional< TimePoint > > timeouts;
	};

} // namespace iter8