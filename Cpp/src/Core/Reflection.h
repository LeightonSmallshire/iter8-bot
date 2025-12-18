#pragma once

#include "magic_enum/magic_enum.hpp"

#include <functional>
#include <variant>
#include <string_view>
#include <source_location>

#define ITER8_FUNC_SIG_STRING                           \
	std::string_view                                    \
	{                                                   \
		std::source_location::current().function_name() \
	}

namespace iter8
{
	namespace detail
	{
		static consteval std::string_view Extract( std::string_view sv, std::string_view prefix, std::string_view suffix )
		{
			auto start = sv.find( prefix );

			if ( start == std::string_view::npos )
				start = 0;
			else
				start += prefix.size();

			auto end = sv.rfind( suffix );
			if ( suffix.empty() || end == std::string_view::npos || end <= start )
				end = sv.size();

			return sv.substr( start, end - start );
		}

		template < typename Type >
		static consteval auto GetLongName() noexcept
		{
#if defined( __clang__ ) || defined( __GNUC__ )
			// Example GCC/Clang __PRETTY_FUNCTION__:
			// "consteval std::string_view detail::GetLongName() [with T = Foo]"
			constexpr std::string_view prefix = "T = ";
			constexpr std::string_view suffix = "]";
			return Extract( ITER8_FUNC_SIG_STRING, prefix, suffix );

#elif defined( _MSC_VER )
			// Example MSVC __FUNCSIG__:
			// "consteval std::string_view __cdecl detail::GetLongName<struct Foo>(void)"
			constexpr std::string_view prefix1 = "GetLongName<";
			constexpr std::string_view prefix2 = "class ";
			constexpr std::string_view prefix3 = "struct ";
			constexpr std::string_view suffix = ">(void)";
			return Extract( Extract( Extract( ITER8_FUNC_SIG_STRING, prefix1, suffix ), prefix2, {} ), prefix3, {} );
#endif
		}

		template < typename Type >
		static consteval auto GetName() noexcept
		{
			std::string_view long_name = GetLongName< Type >();
			auto first = long_name.find_last_of( "::" );
			if ( first == std::string_view::npos )
				first = long_name.find_last_of( ' ' ) + 1; // If npos, will wrap around to zero
			else
				first++;
			return long_name.substr( first, long_name.length() - first );
		}
	} // namespace detail

	/*
		Type Traits for inspecting a given type
	*/

	template < typename T >
	struct TypeTraits
	{
		static constexpr auto QualifiedName = detail::GetLongName< T >();
		static constexpr auto Name = detail::GetName< T >();
		static constexpr auto BaseName = detail::GetName< std::remove_cvref_t< T > >();

		static constexpr bool IsObject = std::is_class_v< T >;
		static constexpr bool IsReference = std::is_reference_v< T >;
		static constexpr bool IsLValueReference = std::is_lvalue_reference_v< T >;
		static constexpr bool IsRValueReference = std::is_rvalue_reference_v< T >;
		static constexpr bool IsPointer = std::is_pointer_v< T >;
		static constexpr bool IsEnum = std::is_enum_v< T >;
		static constexpr bool IsArray = std::is_array_v< T >;
		static constexpr bool IsConst = std::is_const_v< std::remove_reference_t< T > >;
		static constexpr bool IsStandard = std::is_standard_layout_v< T >;

		template < typename R >
		static constexpr bool IsBaseOf = std::is_base_of_v< T, R >;

		template < typename R >
		static constexpr bool IsSameAs = std::is_same_v< T, R >;
	};

	namespace detail
	{

		template < size_t I, typename T, typename TupleType >
		static consteval size_t IndexFunction()
		{
			static_assert( I < std::tuple_size_v< TupleType >, "The element is not in the tuple" );

			using IndexType = typename std::tuple_element< I, TupleType >::type;

			if constexpr ( std::is_same_v< T, IndexType > )
				return I;
			else
				return IndexFunction< I + 1, T, TupleType >();
		}
	} // namespace detail


	/*
		A type list for inspecting a list of types.
	*/

	template < typename... Ts >
	struct TypeList
	{
		static constexpr size_t Size = sizeof...( Ts );

		using TupleType = std::tuple< Ts... >;
		using VariantType = std::variant< Ts... >;
		using VariantTypeWithMonostate = std::variant< std::monostate, Ts... >;

		template < typename R >
		static constexpr bool Contains = std::disjunction_v< std::is_same< R, Ts >... >;

		template < typename R >
		static constexpr size_t Index = detail::IndexFunction< 0, R, TupleType >();

		template < size_t I >
		using Type = std::tuple_element< I, TupleType >::type;

		template < size_t I >
		using Traits = TypeTraits< typename std::tuple_element< I, TupleType >::type >;
	};


	/*
		General purpose conceptzs
	*/

	template < typename T >
	concept IsEnum = TypeTraits< T >::IsEnum;

	template < typename T, typename Base >
	concept DerivedFromOnly = std::derived_from< T, Base > and not std::same_as< T, Base >;

	template < typename T >
	concept IsStandard = std::is_standard_layout_v< T >;

	template < typename T >
	concept IsConst = std::is_const_v< T >;

	template < typename From, typename To >
	concept Castable = requires( From from ) { static_cast< To >( from ); };

	template < typename T >
	concept Integral = std::integral< T >;

	template < typename T >
	concept Numeric = std::is_arithmetic_v< T >;

	template < typename T >
	concept AddAssignable = requires( T&& t ) {
		t += t;
	};

	template < typename T >
	concept UnaryAddable = requires( T&& t ) {
		{ t + t } -> std::convertible_to< T >;
	};

	template < typename T >
	concept Summable = std::is_default_constructible_v< T > and ( AddAssignable< T > or UnaryAddable< T > );

	template < typename T >
	concept UNumeric = std::unsigned_integral< T >;

	template < typename T >
	concept ComparableLess = requires( T&& t1, T&& t2 ) { std::less< T >( t1, t2 ); };

	template < typename T >
	concept ComparableGreater = requires( T&& t1, T&& t2 ) { std::greater< T >( t1, t2 ); };

	template < typename T >
	concept Sizeable = requires( T&& t ) {
		{ std::size( t ) } -> std::convertible_to< size_t >;
	};


	template < typename Func, typename TReturn, typename... TArgs >
	concept IsFunc = std::invocable< Func, TArgs... > and std::convertible_to< std::invoke_result_t< Func, TArgs... >, TReturn >;

	template < typename Func, typename... TArgs >
	concept IsAction = IsFunc< Func, void, TArgs... >;

	template < typename Func, typename... TArgs >
	concept IsPredicate = IsFunc< Func, bool, TArgs... >;


	template < typename H, typename Key >
	concept Hash =
		std::regular_invocable< H const&, Key const& > &&
		std::convertible_to< std::invoke_result_t< H const&, Key const& >, std::size_t >;


	/*
		Function Traits for inspecting a function type
	*/

	template < typename T >
	struct FunctionTraits;

	// std::function specialisation
	template < typename R, typename... Args >
	struct FunctionTraits< std::function< R( Args... ) > >
	{
		using ReturnType = R;
		using Arguments = TypeList< Args... >;
	};

	// Function pointer specialisation
	template < typename R, typename... Args >
	struct FunctionTraits< R ( * )( Args... ) >
	{
		using ReturnType = R;
		using Arguments = TypeList< Args... >;
	};

	// Member function pointer specialisations
	template < typename R, typename O, typename... Args >
	struct FunctionTraits< R ( O::* )( Args... ) >
	{
		using ObjectType = O;
		using ReturnType = R;
		using Arguments = TypeList< Args... >;
	};
	template < typename R, typename O, typename... Args >
	struct FunctionTraits< R ( O::* )( Args... )& >
	{
		using ObjectType = O;
		using ReturnType = R;
		using Arguments = TypeList< Args... >;
	};
	template < typename R, typename O, typename... Args >
	struct FunctionTraits< R ( O::* )( Args... ) && >
	{
		using ObjectType = O;
		using ReturnType = R;
		using Arguments = TypeList< Args... >;
	};
	template < typename R, typename O, typename... Args >
	struct FunctionTraits< R ( O::* )( Args... ) const >
	{
		using ObjectType = O const;
		using ReturnType = R;
		using Arguments = TypeList< Args... >;
	};
	template < typename R, typename O, typename... Args >
	struct FunctionTraits< R ( O::* )( Args... ) const& >
	{
		using ObjectType = O const;
		using ReturnType = R;
		using Arguments = TypeList< Args... >;
	};
	template < typename R, typename O, typename... Args >
	struct FunctionTraits< R ( O::* )( Args... ) const&& >
	{
		using ObjectType = O const;
		using ReturnType = R;
		using Arguments = TypeList< Args... >;
	};


	/*
		Member Traits for inspecting a data member
	*/

	template < typename T >
	struct MemberTraits;

	// Member object pointer specialisation
	template < typename P, typename O >
	struct MemberTraits< P O::* >
	{
		using ObjectType = O;
		using MemberType = P;
	};
} // namespace iter8