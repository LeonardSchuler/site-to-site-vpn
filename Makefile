# Length of password (adjust between 8–64)
PSK_LEN ?= 64

# Target to generate .env with PASSWORD variable
.env:
	@pw=$$(LC_ALL=C tr -dc 'A-Za-z1-9._' </dev/urandom | head -c $(PSK_LEN)); \
	echo "TUN1_PRE_SHARED_KEY=\"$$pw\"" > .env; \
	echo ".env generated with TUN1_PRE_SHARED_KEY"