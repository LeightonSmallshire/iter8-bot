#pragma once

#include "Core/Commands.h"
#include "Database/Connection.h"

#include "dpp/dpp.h"

namespace iter8
{
	struct Context
	{
		dpp::cluster bot;
		db::Connection db;

		std::map< std::string, std::map< std::string, AutocompleteHandler > > autocomplete_handlers;
	};

} // namespace iter8