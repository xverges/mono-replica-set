# Making-of: docker-based MongoDB replica-set migration from single instance

[https://github.com/xverges/mongo-replica-set](https://github.com/xverges/mongo-replica-set)

## Initial situation

- Docker-based. Using 3.4.4. We would be happy to move to something with a later end of life [(3.6 or 4.0 as today)](https://www.mongodb.com/support-policy).
- Code is using PyMongo 3.5.1 [(compatibility char)](https://docs.mongodb.com/ecosystem/drivers/driver-compatibility-reference/#reference-compatibility-mongodb-python)
- Starting point: two disconnected single nodes, with data that needs to be consolidated and
  migrated into a replica set. The mongodb instances have root credentials setup with
  `MONGO_INITDB_ROOT_USERNAME` and additional accounts created with a script in
  `docker-entrypoint-initdb.d`.
- Simplest target configuration: [primary, secondary and arbitrer](https://docs.mongodb.com/manual/core/replica-set-architecture-three-members/#primary-with-a-secondary-and-an-arbiter)


## Vagrant environment to test

- Learned that Vagrant now has a [docker provisioner](https://www.vagrantup.com/docs/provisioning/docker.html)
  and that there is a [docker compose provisioner plugin](https://github.com/leighmcculloch/vagrant-docker-compose).
- So... `vagrant plugin install vagrant-docker-compose`
- Created `first`, `second` and `arbitrer`


## Plan

- Taking advantage of `docker-entrypoint.sh` to run mongo commands is not valid approach:
  it only works on empty instances
- Steps
    - backup: `mongodump` `first` and `second`
    - verify that the backups work
    - consolidate: `mongorestore` `second`'s dump into `first` (alternatively, could `mongoexport` and `mongoimport`)
    - stop `second`. Delete its data folder (Would not do that if I could have [file system snapshot backups](https://docs.mongodb.com/manual/tutorial/backup-with-filesystem-snapshots/))
    - start `second`
    - run 

## A Tangent

I was looking into some simple way to setup/activate a virtualenv associated to the project, and
went jumping from cool project to cool project: from [autoenv](https://github.com/kennethreitz/autoenv)
to [direnv](https://direnv.net/) and finally betting on [Pipenv: Python Development Workflow for
Humans](https://github.com/pypa/pipenv). Thus, the project dependencies are tracked in `Pipfile`.


## Doing. First (half) successful attempt.

Get our python dependencies and the environment variables defined in `.env`.

```
$ pipnenv shell
(mongo-replica-set-qvtM3FSm)$
````

Start the `first` and `second` vagrant boxes and their docker-compose (`vagrant destroy` +
`vagrant up`). Requires installing docker inside the guests, getting the mongodb docker
image... takes its time (15 minute-ish on my home network). 

```
(mongo-replica-set-qvtM3FSm)$ ./scripts/01-start-standalone.sh
```
[<sup>01-start-standalone.sh</sup>](https://github.com/xverges/mongo-replica-set/blob/master/scripts/01-start-standalone.sh)

Reset the boxes. Trial an error required getting to this step very often.
- Stop the docker containers.
- Delete the mongodb data folders
- Recreate the docker containers (by re-provisioning the vagrant box again). The mongodb accounts
specified in a script in `/docker-entrypoint-initdb.d` are created. These scripts won't be
executed once the data folder is not empty.
- Give the `xv_mongo_rw` account privileges to access collections in the `local` database. 

```
(mongo-replica-set-qvtM3FSm)$ ./scripts/reset-standalone.sh all
```
[<sup>reset-standalone.sh</sup>](https://github.com/xverges/mongo-replica-set/blob/master/scripts/reset-standalone.sh)

Create dbs, collections and documents in the `first` and `second` instances

```
(mongo-replica-set-qvtM3FSm)$ ./scripts/02-feed-standalone.py
(mongo-replica-set-qvtM3FSm)$ ./scripts/read-standalone.py
```
[<sup>02-feed-standalone.py</sup>](https://github.com/xverges/mongo-replica-set/blob/master/scripts/02-feed-standalone.py)
[<sup>read-standalone.sh all</sup>](https://github.com/xverges/mongo-replica-set/blob/master/scripts/read-standalone.sh)

Consolidate all the info on the `first`. 
- `mongodump` + `mongorestore` to have everything in the first
- delete the data folder of `second` to remove its contents

```
(mongo-replica-set-qvtM3FSm)$ ./scripts/backup.sh
(mongo-replica-set-qvtM3FSm)$ ./scripts/restore.sh second 192.168.100.10
(mongo-replica-set-qvtM3FSm)$ ./scripts/reset-standalone.sh second
(mongo-replica-set-qvtM3FSm)$ ./scripts/read-standalone.py
```
[<sup>backup.sh</sup>](https://github.com/xverges/mongo-replica-set/blob/master/scripts/backup.sh)
[<sup>restore.sh</sup>](https://github.com/xverges/mongo-replica-set/blob/master/scripts/restore.sh)
[<sup>reset-standalone.sh</sup>](https://github.com/xverges/mongo-replica-set/blob/master/scripts/reset-standalone.sh)
[<sup>read-standalone.sh</sup>](https://github.com/xverges/mongo-replica-set/blob/master/scripts/read-standalone.sh)

Restart the instances, now with the `--replSet` param set and allowing
to have other hosts that `localhost` to connect to mongodb. I allowed
everything with param `--bind_ip 0.0.0.0 `.

Note that, when I specified the `--replSet` param with an empty data directory,
the scripts in `/docker-entrypoint-initdb.d` were not executed.

```
(mongo-replica-set-qvtM3FSm)$ ./scripts/03-stop-standalone.sh
(mongo-replica-set-qvtM3FSm)$ ./scripts/04-start-with-repl-param.sh
```
[<sup>03-stop-standalone.sh</sup>](https://github.com/xverges/mongo-replica-set/blob/master/scripts/03-stop-standalone.sh)
[<sup>04-start-with-repl-param.sh</sup>](https://github.com/xverges/mongo-replica-set/blob/master/scripts/04-start-with-repl-param.sh)

The instances are not operative now. If we try to read them...

```
(mongo-replica-set-qvtM3FSm)$ ./scripts/read-standalone.py
(mongo-replica-set-qvtM3FSm) bash-3.2$ ./scripts/read-standalone.py
----FIRST----
node is not in primary or recovering state
----SECOND----
{'local': {'not_replicated': ()}}
```

...and the reported error is on track:
```
(mongo-replica-set-qvtM3FSm) bash-3.2$ ./scripts/get-replicaset-status.sh
Working with first... Mapped to the host port 27110
MongoDB shell version v3.4.4
connecting to: mongodb://127.0.0.1:27017
MongoDB server version: 3.4.4
{
	"info" : "run rs.initiate(...) if not yet done for the set",
	"ok" : 0,
	"errmsg" : "no replset config has been received",
	"code" : 94,
	"codeName" : "NotYetInitialized"
}
Working with second... Mapped to the host port 27111
MongoDB shell version v3.4.4
connecting to: mongodb://127.0.0.1:27017
MongoDB server version: 3.4.4
{
	"info" : "run rs.initiate(...) if not yet done for the set",
	"ok" : 0,
	"errmsg" : "no replset config has been received",
	"code" : 94,
	"codeName" : "NotYetInitialized"
}
```
[<sup>get-replicaset-status.sh</sup>](https://github.com/xverges/mongo-replica-set/blob/master/scripts/get-replicaset-status.sh)


And, all the previous commands in a single line to make trial-and-error faster:

```
 (mongo-replica-set-qvtM3FSm)$ ./scripts/reset-standalone.sh all && ./scripts/02-feed-standalone.py && ./scripts/backup.sh && ./scripts/restore.sh second 192.168.100.10 && ./scripts/reset-standalone.sh second && ./scripts/03-stop-standalone.sh && ./scripts/04-start-with-repl-param.sh 
 ```

Initialize the replica set. This is done in the [`replicaset-init.js`](https://github.com/xverges/mongo-replica-set/blob/master/docker/mongo-scripts/replicaset-init.template.js)
and [`replicaset-add-additional.js`](https://github.com/xverges/mongo-replica-set/blob/master/docker/mongo-scripts/replicaset-add-additional.template.js)
- It is important to pass the ip of `first`, because, when I used
  `rs.initiate()` without params, the configuration for the primary member of the replica set
  pointed to an unreachable address, and `second` was unable to reach `first`.
- Adding `second` as a second member in the config param of `rs.initiate()` also resulted in
  failure.
- Adding `second` right after `rs.initiate()` could also fail: you have to wait until
  its `stateStr` is set to `PRIMARY`.

```
(mongo-replica-set-qvtM3FSm)$ ./scripts/05-init-replicaset.sh
(mongo-replica-set-qvtM3FSm)$ ./scripts/read-standalone.py
```
[<sup>05-init-replicaset.sh</sup>](https://github.com/xverges/mongo-replica-set/blob/master/scripts/05-init-replicaset.sh)

The arbitrer has not been setup, but we can access both instances. Using the previous connection
params, that do not specify anything related to the replicaset:
- we can read from both instances
- we can update the primary (that is replicated to the secondary)
- we get a failure when updating the secondary (`pymongo.errors.NotMasterError: not master`)

## Networking issues

When trying to use the `replicaset` param when creating `MongoClient`, I learned that my OSX host
can not reach my VirtualBox guests, or my guests reach the
[hostonly](https://blogs.oracle.com/scoter/networking-in-virtualbox-v2#Host-only) address where I
expected my host to be. Lots of googling but nothing helped.

For the record:

```
$ VBoxManage list hostonlyifs

...

Name:            vboxnet2
GUID:            786f6276-656e-4274-8000-0a0027000002
DHCP:            Disabled
IPAddress:       192.168.100.1
NetworkMask:     255.255.255.0
IPV6Address:
IPV6NetworkMaskPrefixLength: 0
HardwareAddress: 0a:00:27:00:00:02
MediumType:      Ethernet
Wireless:        No
Status:          Up
VBoxNetworkName: HostInterfaceNetworking-vboxnet2
```

```
$ ifconfig
...
vboxnet2: flags=8943<UP,BROADCAST,RUNNING,PROMISC,SIMPLEX,MULTICAST> mtu 1500
  ether 0a:00:27:00:00:02
  inet 192.168.100.1 netmask 0xffffff00 broadcast 192.168.100.255
...
```


```
$ VBoxManage showvminfo mongo-replica-set_arbitrer_1537298209734_479
...
Guest OS:        Red Hat (64-bit)
...
NIC 1:           MAC: 08002737F846, Attachment: NAT, Cable connected: on, Trace: off (file: none), Type: 82540EM, Reported speed: 0 Mbps, Boot priority: 0, Promisc Policy: deny, Bandwidth group: none
NIC 1 Settings:  MTU: 0, Socket (send: 64, receive: 64), TCP Window (send:64, receive: 64)
NIC 1 Rule(0):   name = ssh, protocol = tcp, host ip = 127.0.0.1, host port = 2201, guest ip = , guest port = 22
NIC 1 Rule(1):   name = tcp27112, protocol = tcp, host ip = , host port = 27112, guest ip = , guest port = 27017
NIC 2:           MAC: 080027EA7320, Attachment: Host-only Interface 'vboxnet2', Cable connected: on, Trace: off (file: none), Type: 82540EM, Reported speed: 0 Mbps, Boot priority: 0, Promisc Policy: allow-all, Bandwidth group: none
...
Guest:

Configured memory balloon size:      0 MB
OS type:                             Linux26_64
Additions run level:                 2
Additions version:                   5.1.26 r117224

Guest Facilities:

Facility "VirtualBox Base Driver": active/running (last update: 2018/09/18 19:17:03 UTC)
Facility "VirtualBox System Service": active/running (last update: 2018/09/18 19:17:06 UTC)
Facility "Seamless Mode": not active (last update: 2018/09/18 19:17:03 UTC)
Facility "Graphics Mode": not active (last update: 2018/09/18 19:17:03 UTC)
```

## Connecting to the replica set from a proper network host

The vagrant boxes see each other, and there we can connect to mongo specifying that we are
connecting to a replica set:

```
MongoClient(url_to_local, replicaset=replicaset_name, read_preference=ReadPreference.NEAREST)
```

We can read and write using this client, from both the box that has the primary and the box that
has the secondary.

## Working with proper credentials and with the local database

So far the tests have been run using mongo root's credentials and regular databases. We now need
to verify that we can work with less privileged credentials and with the local databases. We will

- add a script that sets up the permissions to be able to use the local database
- use non-root credentials to read and update the database and the replicaset

The tests show that

- the `local` database can be updated when using the secondary and no replicaset specification
- the `local` database of the secondary WON'T be updated if we specify a replicaset.

## Wrap up

- Migrate to `local` the databases that we don't want replicated
- Modify the code to have different ways to create the `pymongo.MongoClient` if we are targeting
  the `local` database or a database that we want replicated
- Use `mongodump` to create a backup of the two instances
- Use `mongorestore` to consolidate all the info in first
- Stop the servers
- Delete the data volume of the second server
- Create and make available the shared key
- Start the servers, specifying `--keyFile`, `--bind_ip` and `--replSet` params for the mongodb container
- Run `rs.initiate()` on the first server
- Wait for the first to be `PRIMARY` and then add the rest of servers: `rs.add()` and `rs.addArb()`
- Modify and deploy the code that specifies that replicaset when creating a `pymongo.MongoClient` to be used for
  databases that we want replicated  


 
