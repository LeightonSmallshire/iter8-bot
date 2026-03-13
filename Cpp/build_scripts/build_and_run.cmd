pushd "%~dp0.."

:: so windows can emulate ARM platforms for compiling
docker run --privileged --rm tonistiigi/binfmt --install all || exit /b %errorlevel%

:: build for both ARM and AMD 64-bit
@REM default builder
@REM docker build -f Dockerfile2 -t bot . || exit /b %errorlevel%
@REM docker buildx build --platform linux/amd64 -f Dockerfile2 -t bot . || exit /b %errorlevel%
docker buildx build --platform linux/arm64 -f Dockerfile2 -t bot . || exit /b %errorlevel%
@REM docker buildx build --platform linux/arm64,linux/amd64 -f Dockerfile2 -t bot . || exit /b %errorlevel%

:: run locally, use .env from this folder
docker run -it --rm --env-file "%~dp0.env" bot || exit /b %errorlevel%

popd
