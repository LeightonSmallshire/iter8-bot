docker build -f Dockerfile2 -t bot . ; if ($?) { docker save bot:latest -o bot.tar }
