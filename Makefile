

.PHONY: test
test:
	docker-compose run --entrypoint=pytest test -s
