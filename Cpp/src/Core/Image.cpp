#include "Image.h"

#define STB_IMAGE_WRITE_IMPLEMENTATION
#include <stb_image_write.h>

namespace iter8
{
	std::vector< std::byte > MakeImageData( std::uint32_t colour )
	{
		constexpr int width = 128;
		constexpr int height = 128;

		std::vector< std::byte > out_png{};

		std::vector< std::uint8_t > pixels( width * height * 4 );

		std::uint8_t const r = ( colour >> 24 ) & 0xFF;
		std::uint8_t const g = ( colour >> 16 ) & 0xFF;
		std::uint8_t const b = ( colour >> 8 ) & 0xFF;
		std::uint8_t const a = ( colour >> 0 ) & 0xFF;

		for ( int i = 0; i < width * height; ++i )
		{
			pixels[ i * 4 + 0 ] = r;
			pixels[ i * 4 + 1 ] = g;
			pixels[ i * 4 + 2 ] = b;
			pixels[ i * 4 + 3 ] = a;
		}

		auto write_callback = []( void* context, void* data, int size ) {
			auto* vec = static_cast< std::vector< std::byte >* >( context );
			auto* bytes = static_cast< std::byte* >( data );

			vec->reserve( vec->size() + size );
			for ( int i = 0; i < size; ++i )
			{
				vec->push_back( bytes[ i ] );
			}
		};

		int comp = 4; // RGBA
		int stride_bytes = width * 4;

		stbi_write_png_to_func(
			write_callback,
			&out_png,
			width,
			height,
			comp,
			pixels.data(),
			stride_bytes );

		return out_png;
	}
} // namespace iter8