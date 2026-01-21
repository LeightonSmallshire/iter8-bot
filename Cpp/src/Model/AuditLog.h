#pragma once

#include "Database/Model.h"
#include <string>
#include <optional>


namespace iter8
{
	struct AuditLogEntry
	{
		db::ID id;								  // PK
		uint64_t target_id;						  // Affected entity
		uint64_t user_id;						  // User
		dpp::audit_type action_type;			  //
		std::optional< std::string > reason;	  //
		std::optional< std::string > extras_blob; //
	};

	struct AuditLogChange
	{
		db::ID id;								// FK → AuditLogEntry.id
		std::string key;						// e.g. "name", "permissions"
		std::optional< std::string > old_value; //
		std::optional< std::string > new_value; //
	};
} // namespace iter8
