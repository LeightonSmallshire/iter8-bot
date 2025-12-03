#pragma once

#include "Database/Model.h"

namespace iter8
{
	struct User
	{
		db::ID id{};
		int count{};
		double duration{};
		double credit{};
	};
}