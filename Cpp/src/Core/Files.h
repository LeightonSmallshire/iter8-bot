#pragma once

#include <filesystem>

namespace iter8
{
	std::vector< char > ReadFileBinary( std::filesystem::path const& path );
	std::filesystem::path CompressDirectory( std::filesystem::path const& dir );
}