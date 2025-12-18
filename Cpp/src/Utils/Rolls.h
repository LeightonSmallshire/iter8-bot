#pragma once

#include "dpp/dpp.h"

namespace iter8::roll
{
	dpp::task< dpp::snowflake > DoRoleRoll(
		dpp::interaction_create_t const& event,
		dpp::snowflake role_id,
		std::vector< dpp::guild_member > const& table,
		std::string_view title,
		std::format_string< std::string, std::string > mod_response, 
		std::format_string< std::string > no_mod_response );
	
}