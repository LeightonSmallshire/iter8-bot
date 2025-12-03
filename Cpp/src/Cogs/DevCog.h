#pragma once

#include "Cog.h"

namespace iter8
{
	class DevCog : public Cog
	{
	public:
		DevCog( Context& ctx ); 

		dpp::task< void > OnGetLogs( dpp::slashcommand_t const& event );
		dpp::task< void > OnDownload( dpp::slashcommand_t const& event );
		dpp::task< void > OnCrash( dpp::slashcommand_t const& event );

		dpp::task< void > OnDownloadAutocomplete( dpp::autocomplete_t const& e, dpp::command_option const& opt );
	};
}