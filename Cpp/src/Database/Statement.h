#pragma once

#include <sqlite3.h>

namespace iter8::db
{
	struct Statement
	{
		sqlite3_stmt* handle{ nullptr };

		Statement() = default;
		explicit Statement( sqlite3_stmt* stmt )
			: handle( stmt )
		{}

		Statement( Statement const& ) = delete;
		Statement& operator=( Statement const& ) = delete;

		Statement( Statement&& other ) noexcept
			: handle( other.handle )
		{
			other.handle = nullptr;
		}
		Statement& operator=( Statement&& other ) noexcept
		{
			if ( this != &other )
			{
				finalize();
				handle = other.handle;
				other.handle = nullptr;
			}
			return *this;
		}

		~Statement()
		{
			finalize();
		}

		void finalize()
		{
			if ( handle )
			{
				sqlite3_finalize( handle );
				handle = nullptr;
			}
		}

		explicit operator bool() const noexcept
		{
			return handle != nullptr;
		}
	};
}