#pragma once

#include <concepts>
#include <random>
#include <ranges>
#include <stdexcept>
#include <iterator>

namespace iter8
{
	class RandomGenerator
	{
	public:
		RandomGenerator() = default;
		RandomGenerator( std::mt19937::result_type seed )
		{
			rng_.seed( seed );
		}

		template < std::integral Int >
		Int operator()( Int upper )
		{
			if ( upper <= 0 )
			{
				throw std::out_of_range( "Random::operator(upper): upper must be > 0" );
			}
			std::uniform_int_distribution< Int > dist( 0, upper - 1 );
			return dist( rng_ );
		}

		template < std::integral Int >
		Int operator()( Int lower, Int upper )
		{
			if ( !( lower < upper ) )
			{
				throw std::out_of_range( "Random::operator(lower, upper): require lower < upper" );
			}
			std::uniform_int_distribution< Int > dist( lower, upper - 1 );
			return dist( rng_ );
		}

		template < std::ranges::forward_range Range >
		auto& operator()( Range&& range )
		{
			auto n = std::ranges::distance( range );
			if ( n <= 0 )
			{
				throw std::out_of_range( "Random::operator(range): range must be non-empty" );
			}

			using index_type = std::ranges::range_difference_t< Range >;
			index_type idx = this->operator()( n );
			auto it = std::ranges::next( std::ranges::begin( range ), idx );
			return *it;
		}

	private:
		std::mt19937 rng_{ std::random_device{}() };
	};

	inline RandomGenerator Random;
}