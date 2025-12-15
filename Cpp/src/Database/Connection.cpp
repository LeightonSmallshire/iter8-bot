#include "Connection.h"
#include "Connection.h"
#include "Connection.h"

namespace iter8::db
{
	Connection::Transaction::Transaction( Connection* db, Mode mode )
		: db_( db )
	{
		switch ( mode )
		{
			case Mode::Deferred:
				db_->ExecRaw( "BEGIN DEFERRED;" );
				break;
			case Mode::Immediate:
				db_->ExecRaw( "BEGIN IMMEDIATE;" );
				break;
			case Mode::Exclusive:
				db_->ExecRaw( "BEGIN EXCLUSIVE;" );
				break;
		}

		active_ = true;
	}

	Connection::Transaction::~Transaction()
	{
		Rollback();
	}

	void Connection::Transaction::Commit()
	{
		if ( !active_ )
			return;
		db_->ExecRaw( "COMMIT;" );
		active_ = false;
	}

	void Connection::Transaction::Rollback() noexcept
	{
		if ( !active_ )
			return;

		db_->ExecRaw( "ROLLBACK;" );
		active_ = false;
	}
} // namespace iter8::db