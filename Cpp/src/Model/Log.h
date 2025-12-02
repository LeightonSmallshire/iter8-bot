#pragma once

#include "Database/Model.h"

#include <spdlog/spdlog.h>

namespace iter8
{
	struct Log
	{
		db::ID id{};
		spdlog::log_clock::time_point timestamp{};
		spdlog::level::level_enum level;
		std::string message;
	};
} // namespace iter8