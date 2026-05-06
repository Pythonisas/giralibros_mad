.PHONY: test run shell migrate upgrade deploy sql prod-db-pull prod-img-pull

flask=uv run flask

test:
	uv run pytest

run:
	FLASK_ENV=development $(flask) run

shell:
	$(flask) shell

migrate:
	$(flask) db migrate

upgrade:
	$(flask) db upgrade

BRANCH ?= main
deploy:
	ssh $(SSH) "cd /home/libros/giralibros/ &&\
		git fetch &&\
		git checkout $(BRANCH) &&\
		git pull origin $(BRANCH) --ff-only &&\
		sudo su libros -l -c \"cd ~/giralibros && uv sync && uv run flask db upgrade\" &&\
		sudo systemctl restart gunicorn"

sql:
	sqlite3 -cmd ".open db.sqlite3"

prod-db-pull:
	scp $(SSH):/home/libros/giralibros/db.sqlite3 db.sqlite3

prod-img-pull:
	rsync -avz $(SSH):/var/www/giralibros/media/ ./media/
