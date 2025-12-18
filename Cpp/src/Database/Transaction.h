#pragma once

namespace iter8::db
{
	class Transaction
	{
	public:
		enum class Mode
		{
			Deferred,
			Immediate,
			Exclusive
		};

		explicit Transaction( class Connection* db, Mode mode = Mode::Immediate );

		~Transaction();

		Transaction( Transaction const& ) = delete;
		Transaction& operator=( Transaction const& ) = delete;

		void Commit();

		void Rollback() noexcept;

	private:
		class Connection* db_{};
		bool active_{};
	};
}