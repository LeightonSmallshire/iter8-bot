#pragma once

#include "dpp/dpp.h"
#include "Database/Connection.h"

namespace iter8
{
	struct Context
	{
		dpp::cluster bot;
		db::Connection db;
	};

}