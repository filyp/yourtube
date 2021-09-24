cd $HOME/.yourtube
wget "https://neo4j.com/artifact.php?name=neo4j-community-4.3.4-unix.tar.gz" -O "neo4j.tar.gz"
tar -xf neo4j.tar.gz
rm neo4j.tar.gz
mv neo4j-community-4.3.4 neo4j

# set the password to yourtube
# maybe use cmd argument to set the password
~/.yourtube/neo4j/bin/neo4j-admin set-initial-password yourtube

# to run:
# ~/.yourtube/neo4j/bin/neo4j start

# TODO describe this step in readme

# TODO add constraints when installing

# to run on manjaro I had to run:
# sudo archlinux-java set java-11-openjdk
