#pragma once
#include <stdint.h>

// HTTP: :80 의 /, /capture, /status 와 :81 의 /stream (MJPEG, 최신 프레임만).
bool http_begin();
int http_stream_clients();
