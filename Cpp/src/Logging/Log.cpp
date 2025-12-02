#include "Log.h"

#include "Database/Connection.h"
#include "Model/Log.h"

#include <spdlog/common.h>
#include <spdlog/sinks/stdout_color_sinks.h>
#include <spdlog/sinks/basic_file_sink.h>

#ifndef GIT_COMMIT_HASH
#define GIT_COMMIT_HASH "NoHashFound"
#endif

namespace iter8::log
{
	static std::shared_ptr< spdlog::logger > logger_;

	class DbLogSink : public spdlog::sinks::base_sink< std::mutex >
	{
	public:
		DbLogSink( db::Connection& db )
			: db_{ db }
		{
		}

	protected:
		void sink_it_( spdlog::details::log_msg const& msg ) override
		{
			logs_.emplace_back( db::ID::Zero, msg.time, msg.level, std::string( msg.payload.data(), msg.payload.size() ) );
		}

		void flush_() override
		{
			db_.Insert( logs_ );
			logs_.clear();
		}

	private:
		db::Connection& db_;
		std::vector< Log > logs_;
	};

	void Init( db::Connection& db )
	{
		std::vector< spdlog::sink_ptr > log_sinks;
		log_sinks.emplace_back( std::make_shared< spdlog::sinks::stdout_color_sink_mt >() );
		log_sinks.emplace_back( std::make_shared< spdlog::sinks::basic_file_sink_mt >( std::format( "data/log-{}.txt", GIT_COMMIT_HASH ), true ) );
		log_sinks.emplace_back( std::make_shared< DbLogSink >( db ) );

		log_sinks[ 0 ]->set_pattern( "%^[%T] %n: %v%$" );
		log_sinks[ 1 ]->set_pattern( "[%T] [%l] %n: %v" );
		log_sinks[ 2 ]->set_pattern( "[%T] [%l] %n: %v" );

		logger_ = std::make_shared< spdlog::logger >( "iter8", begin( log_sinks ), end( log_sinks ) );
		spdlog::register_logger( logger_ );
		logger_->set_level( spdlog::level::trace );
		logger_->flush_on( spdlog::level::trace );
	}

	namespace detail
	{
		std::shared_ptr< spdlog::logger >& GetLogger()
		{
			return logger_;
		}
	} // namespace detail
} // namespace iter8::log
