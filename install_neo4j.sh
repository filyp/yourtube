#!/usr/bin/env bash
set -e

# TODO describe this step in readme

echo "\n\nDownload and install neo4j"
mkdir -p $HOME/.yourtube
cd $HOME/.yourtube
wget "https://neo4j.com/artifact.php?name=neo4j-community-4.3.4-unix.tar.gz" -O "neo4j.tar.gz"
tar -xf neo4j.tar.gz
rm neo4j.tar.gz
mv neo4j-community-4.3.4 neo4j

echo "\n\nInstall JDK 11"
. /etc/os-release
if [[ "$NAME" == "Ubuntu" ]]; then
    sudo apt install openjdk-11-jdk
else
    echo "Make sure openjdk-11 is installed"
    # to run on manjaro I had to run:
    # sudo archlinux-java set java-11-openjdk
fi

# TODO maybe use cmd argument to set the password
echo "\n\nSet the password for neo4j"
~/.yourtube/neo4j/bin/neo4j-admin set-initial-password yourtube

echo "\n\nRun neo4j"
~/.yourtube/neo4j/bin/neo4j start
sleep 5

echo "\n\nSet up database"
yourtube-prepare-db

echo "\n\nInstalled successfully"
