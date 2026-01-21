#pragma once

#include "Database/Model.h"

#include <spdlog/spdlog.h>

namespace iter8
{
	struct Log
	{
		db::ID id{};
		TimePoint timestamp{};
		spdlog::level::level_enum level;
		std::string message;
	};
} // namespace iter8
