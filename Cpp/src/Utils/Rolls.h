#pragma once

#include "dpp/dpp.h"

namespace iter8::roll
{
	dpp::task< dpp::snowflake > DoRoleRoll(
		dpp::interaction_create_t& event,
		dpp::snowflake role_id,
		std::vector< dpp::guild_member > const& table,
		std::string_view title,
		std::pair< std::format_string< std::string, std::string >, std::format_string< std::string > > response );
	
	static consteval std::pair< std::format_string< std::string, std::string >, std::format_string< std::string > > MakeResponsePair( std::string_view a, std::string_view b )
	{
		return std::make_pair< std::format_string< std::string, std::string >, std::format_string< std::string > >( a, b );
	}
}