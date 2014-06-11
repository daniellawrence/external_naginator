![Travis](https://api.travis-ci.org/daniellawrence/external_naginator.svg)

Install
-------

```sh
mkvirtualenv external_naginator
pip install -r requirements.txt
```

Configuration
----------------

You will need to change the following.

    generate_poc.py PUPPET_HOST
	fabfile.py      env.host_string


Generate the nagios configuraiton
----------------------------------------

```sh
./generate_poc.py
```

Generate and push it to your nagios server
------------------------------------------

    $ pip install fabric
    $ fab deploy
