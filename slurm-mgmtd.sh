#!/bin/bash

function iptodns()
{
	echo $1 | tr "\." "-" | xargs -I {} echo ip-{}
}

RELEASE=unknown

if [ -f /etc/system-release ]; then
   if grep -q "CentOS" /etc/system-release; then
      RELEASE=centos
   elif grep -q "Red" /etc/system-release; then
      RELEASE=rhel
   elif grep -q "Amazon" /etc/system-release; then
      RELEASE=amazon
   fi
elif lsb_release -d | grep -q "Ubuntu"; then
   RELEASE=ubuntu
   echo "Slurm Install on Ubuntu/Debian is not supported at this moment"
   exit 0
fi

echo $RELEASE

# Setup NFS
echo "/nfs *(rw,async,no_subtree_check,no_root_squash)" | sudo tee /etc/exports
sudo systemctl enable nfs
sudo systemctl start nfs
sudo exportfs -av

# Setup MUNGE

if [ $RELEASE == "centos" ] || [ $RELEASE == "rhel" ]; then
   sudo yum --nogpgcheck install epel-release -y
   sudo yum --nogpgcheck install munge munge-libs munge-devel -y
elif [ $RELEASE == "amazon" ]; then
   sed -i "s|enabled=0|enabled=1|g" /etc/yum.repos.d/epel.repo
   sudo yum install munge munge-libs munge-devel -y
fi


echo "welcometoslurmamazonuserwelcometoslurmamazonuserwelcometoslurmamazonuser" | sudo tee /etc/munge/munge.key
sudo chown munge:munge /etc/munge/munge.key
sudo chmod 600 /etc/munge/munge.key
sudo chown -R munge /etc/munge/ /var/log/munge/
sudo chmod 0700 /etc/munge/ /var/log/munge/
sudo systemctl enable munge
sudo systemctl start munge
sleep 5

#Setup SLURM
sudo yum install openssl openssl-devel pam-devel numactl numactl-devel hwloc hwloc-devel lua lua-devel readline-devel rrdtool-devel ncurses-devel man2html libibmad libibumad rpm-build -y
sudo yum groupinstall "Development Tools" -y

sudo chown centos:centos /home/centos/slurm-*.tar.bz2
tar -xvf /home/centos/slurm-*.tar.bz2 -C /home/centos
cd /home/centos/slurm-*
/home/centos/slurm-*/configure --prefix=/nfs/slurm
make -j 4
sudo make install

sleep 5
export SLURM_HOME=/nfs/slurm

sudo -E mkdir -p $SLURM_HOME/etc/slurm
sudo -E cp /home/centos/slurm-*/etc/* $SLURM_HOME/etc/slurm
sudo -E cp $SLURM_HOME/etc/slurm/slurmd.service /lib/systemd/system
sudo -E cp $SLURM_HOME/etc/slurm/slurmctld.service /lib/systemd/system

sudo -E cp /home/centos/slurm.conf $SLURM_HOME/etc/
sudo -E mkdir -p $SLURM_HOME/etc/slurm.conf.d
sudo -E sed -i "s|@HEADNODE@|$HOSTNAME|g" $SLURM_HOME/etc/slurm.conf

echo 'SLURM_HOME=/nfs/slurm' | sudo tee /etc/profile.d/slurm.sh
echo 'SLURM_CONF=$SLURM_HOME/etc/slurm/slurm.conf' | sudo tee -a /etc/profile.d/slurm.sh
echo 'PATH=$SLURM_HOME/bin:$PATH' | sudo tee -a /etc/profile.d/slurm.sh

sudo -E mkdir -p /var/spool/slurm
#echo "include *.conf" | sudo tee -a $SLURM_HOME/etc/slurm.conf.d/slurm_nodes.conf
sudo cp /home/centos/slurm-aws* $SLURM_HOME/bin
sudo chmod +x $SLURM_HOME/bin/slurm-aws*
#echo `/nfs/slurm/sbin/slurmd -C` | cut -d " " -f1,2,5,6,7 | sudo tee -a $SLURM_HOME/etc/slurm.conf.d/slurm_nodes.conf

azs=$2
ranges=$3

IFS=',' read -r -a azs_arr <<< "$azs"
IFS=',' read -r -a ranges_arr <<< "$ranges"
num_ranges=`printf '%s\n' "${ranges_arr[@]}" | wc -w`

for ((i =0; i < $num_ranges; i++)); do
   echo NodeName=@RANGE@ CPUs=8 Feature=@AZ@ State=Cloud | sudo tee -a $SLURM_HOME/etc/slurm.conf.d/slurm_nodes.conf
   sudo -E sed -i "s|@RANGE@|${ranges_arr[i]}|g" $SLURM_HOME/etc/slurm.conf.d/slurm_nodes.conf
   sudo -E sed -i "s|@AZ@|${azs_arr[i]}|g" $SLURM_HOME/etc/slurm.conf.d/slurm_nodes.conf
done

export IPADDR=$(curl -sS http://169.254.169.254/latest/meta-data/local-ipv4)
sudo -E sed -i "s|@IP@|$IPADDR|g" $SLURM_HOME/etc/slurm.conf
export IPADDR_N=$(iptodns $IPADDR)
sudo -E sed -i "s|@EXC@|$IPADDR_N|g" $SLURM_HOME/etc/slurm.conf

sudo systemctl enable slurmctld
sudo systemctl start slurmctld

