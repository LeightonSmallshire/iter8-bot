docker build -f Dockerfile2 -t bot . ; if ($?) { docker run -it --rm bot }
