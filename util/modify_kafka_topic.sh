#!/bin/bash
#
set -e
set -o pipefail

function log_info() {
  local message="$@"
  echo "[INFO] $message"
}
function log_warning() {
  local message="$@"
  echo "[WARNING] $message" >&2
}
function log_error() {
  local message="$@"
  echo "[ERROR] $message" >&2
}
function die_exit() {
  local message="$@"
  echo "[CRITICAL] $message" 1>&2
  exit 111
}
function isCygwin() {
  local os=$(uname -s)
  case "$os" in
    CYGWIN*) return 0 ;;
    *)  return 1 ;;
  esac
}


###
function get_topics() {
  topics=$($getTopicCommand --bootstrap-server $bootstrapServerHost --list)
}

function filter_topic() {
  # 位置参数1，用于判断 topic 副本数
  rn=$1
  if [ -z "$rn" ];then
    die_exit "filter replica number can not be null, check and retry."
  fi
  # 获取所有 topic，过滤小于等于 $rn 的所有 topic
  get_topics
  echo "" > ./topic.txt
  for topic in $topics;do
    replicaNumber=$($getTopicCommand --bootstrap-server $bootstrapServerHost --describe --topic "$topic"|grep ReplicationFactor|awk -F'[ :\t]+' '{print $8}')
    if [[ "$replicaNumber" -le $rn ]];then
      echo "$topic" >> ./topic.txt
    fi
  done
  # 生成重分配 json 文件结果
  filterResult=$?
  if [ $filterResult -ne 0 ];then
    die_exit "filter topic error, please check."
  fi
  # 去除空行
  sed -i '/^$/d' ./topic.txt
  filterTopics=$(cat ./topic.txt)
}

function reassign_partition(){
  # template.json 文件是否存在
  if [ ! -e /tmp/template.json ];then
    die_exit "template.json not exists, check and retry."
  fi
  # 过滤 topic 副本数小于等于3的所有 topic
  filter_topic 3
  # 生成重分配 json 文件
  for topic in $filterTopics;do
    sed -e "s#template#$topic#g" /tmp/template.json > "$topic".json
  done
  generateResult=$?
  if [ $generateResult -ne 0 ];then
    die_exit "generate json file error, please check."
  fi
  # 根据生成的 json 文件重分配 topic
  # consumer topic 无法重分配 3分区，过滤掉单独处理
  for jsonFile in $(ls | grep json| grep -Ev "grep|consumer_offset");do
    $reassignPartitionCommand --bootstrap-server $bootstrapServerHost --reassignment-json-file "$jsonFile" --execute
  done
}

##### template.json #####
#{
#    "version": 1,
#    "partitions": [
#        {"topic": "template", "partition": 0,"replicas": [1,2,3]},
#        {"topic": "template", "partition": 1,"replicas": [2,3,1]},
#        {"topic": "template", "partition": 2,"replicas": [3,1,2]}
#    ]
#}
##### template.json #####

brokers=(1 2 3)
bootstrapServerHost=172.23.1.3:9092
baseCommandDir=/opt/uat_kafka/bin
getTopicCommand=${baseCommandDir}/kafka-topics.sh
reassignPartitionCommand=${baseCommandDir}/kafka-reassign-partitions.sh

reassign_partition
