#pragma once

#include "User.h"

#include "Database/Model.h"

namespace iter8
{
	struct Gift
	{
		db::ID id;
		float value;
		db::ForeignKey< User > gifter_id;
		db::ForeignKey< User > recipient_id;
	};
}