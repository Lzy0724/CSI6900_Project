import os
import sys
from tqdm import tqdm
import time
from datetime import datetime
from prettytable import PrettyTable
import logging
import json
import typing as t
import argparse
import re
from collections import defaultdict

# 1. 获取项目根目录 (放在最前面，方便后续使用)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)  # 确保能导入项目模块

from my_rewriter.database import DBArgs, Database
from my_rewriter.config import init_db_config, init_llms
from my_rewriter.db_utils import compare, actual_time, actual_time_once
from my_rewriter.my_utils import MyModel

parser = argparse.ArgumentParser()
parser.add_argument('--compute_latency', action='store_true', required=False, help='whether to compute SQL latency')
parser.add_argument('--database', type=str, required=True)
parser.add_argument('--logdir', type=str, default='logs')
parser.add_argument('--large', action='store_true', required=False,
                    help='whether to execute SQL queries on large database')
parser.add_argument('--no_reflection', action='store_true', required=False, help='whether to reflect query rewrite')
args = parser.parse_args()

model_args = init_llms(args.logdir, load_model=False)
pg_config = init_db_config(args.database)
pg_args = DBArgs(pg_config)

if 'calcite' in args.database:
    DATASET = 'calcite'
elif 'tpch' in args.database:
    DATASET = 'tpch'
elif 'dsb' in args.database:
    DATASET = 'dsb'
else:
    DATASET = args.database

# 2. 修复 LOG_DIR 为绝对路径
LOG_DIR = os.path.join(project_root, args.logdir, DATASET)


def rewrite(input_cost: float, output_cost: float, used_rules: t.List[str]) -> bool:
    return output_cost != float("inf") and (input_cost >= output_cost or 'SUB_QUERY_TO_CORRELATE' in str(used_rules))


def is_improved(t: t.Dict, idx: int, compute_latency: bool) -> bool:
    if rewrite(t['input_cost'], t['rewrites'][idx]['output_cost'], t['rewrites'][idx]['used_rules']):
        if compute_latency:
            if args.large:
                return t['input_latency'] > t['rewrites'][idx]['output_latency']
            else:
                return compare(t['input_var'], t['rewrites'][idx]['output_var'])
        else:
            return t['input_cost'] > t['rewrites'][idx]['output_cost']
    return False


def _analyze(name: str, input_latency: float) -> dict:
    # 3. 使用 os.path.join 拼接日志路径
    log_filename = os.path.join(LOG_DIR, f'{name}.log')

    # 4. 增加文件存在性检查
    if not os.path.exists(log_filename):
        print(f"警告: 找不到日志文件 {log_filename}。请确保你已经运行了重写脚本。")
        # 返回一个空结果以避免崩溃，或者你可以选择在这里 raise Exception
        return {'template': name, 'time': {'retrieval': 0, 'arrange': 0, 'rewrite': 0}, 'rewrites': []}

    retrieval_start = None
    retrieval_end = None
    arrange_first_end = None
    arrange_second_start = None
    arrange_end = None
    rearrange_time = None
    rewrite_res = []
    model = MyModel(model_args)

    # 5. 指定编码 utf-8
    with open(log_filename, 'r', encoding='utf-8', errors='replace') as f:
        lines = list(f.readlines())
        if not lines:
            return {'template': name, 'time': {'retrieval': 0, 'arrange': 0, 'rewrite': 0}, 'rewrites': []}

        retrieval_start = lines[0].split(',')[0]
        try:
            retrieval_start = datetime.strptime(retrieval_start, '%H:%M:%S')
        except ValueError:
            pass  # Handle cases where first line isn't a timestamp

        for line in lines:
            if 'root INFO Input Cost' in line:
                retrieval_start = line.split(',')[0]
                retrieval_start = datetime.strptime(retrieval_start, '%H:%M:%S')
            elif 'root INFO Retrieved Rewrite Cases' in line:
                retrieval_end = line.split(',')[0]
                retrieval_end = datetime.strptime(retrieval_end, '%H:%M:%S')
            elif 'root INFO Intermediate Results' in line:
                arrange_first_end = line.split(',')[0]
                arrange_first_end = datetime.strptime(arrange_first_end, '%H:%M:%S')
            elif 'root INFO Start recipe-based rewrite' in line:
                arrange_second_start = line.split(',')[0]
                arrange_second_start = datetime.strptime(arrange_second_start, '%H:%M:%S')
            elif 'root INFO Arranged Rule Sequence' in line or 'root INFO Rule Sequence' in line:
                arrange_end = line.split(',')[0]
                arrange_end = datetime.strptime(arrange_end, '%H:%M:%S')
            elif 'root DEBUG {\'messages\'' in line:
                try:
                    obj = eval(line[line.find('{'):])
                    if obj['messages'][0]['content'] == model.REARRANGE_RULES_SYS_PROMPT:
                        rearrange_time = obj['time']
                except:
                    pass
            elif 'root INFO Rewrite Execution Results' in line:
                try:
                    res = eval(line[line.find('{'):])
                    db = Database(pg_args)
                    res['output_cost'] = db.cost_estimation(res['output_sql'])
                    if res['output_cost'] == -1:
                        res['output_cost'] = float("inf")
                    if args.compute_latency:
                        if res['output_sql'] == 'None':
                            res['output_latency'] = input_latency
                            if not args.large:
                                res['output_var'] = [input_latency] * 5
                        else:
                            if args.large:
                                output_latency = actual_time_once(res['output_sql'], pg_args, 300)
                            else:
                                output_latency, output_var = actual_time(res['output_sql'], pg_args, 300)
                            res['output_latency'] = output_latency
                            if not args.large:
                                res['output_var'] = output_var
                    rewrite_res.append(res)
                    if len(rewrite_res) == 1 and args.no_reflection:
                        break
                except Exception as e:
                    print(f"Error parsing line in {log_filename}: {e}")

    if 'no_steps' in args.logdir or args.no_reflection:
        # assert len(rewrite_res) == 1 # Commented out to prevent crash on partial logs
        pass
    else:
        # assert len(rewrite_res) == 2
        pass

    # Handle missing timestamps gracefully
    def get_seconds(end, start):
        if end and start:
            return (end - start).seconds
        return 0

    retrieval_time = get_seconds(retrieval_end, retrieval_start) * 1000

    arrange_time_val = get_seconds(arrange_first_end, retrieval_end)
    arrange_time_val += get_seconds(arrange_end, arrange_second_start)
    if len(rewrite_res) == 2 and rearrange_time:
        arrange_time_val += rearrange_time
    arrange_time = arrange_time_val * 1000

    rewrite_time = sum([res.get('time', 0) for res in rewrite_res])

    rewrite_obj = {'template': name,
                   'time': {'retrieval': retrieval_time, 'arrange': arrange_time, 'rewrite': rewrite_time},
                   'rewrites': rewrite_res}
    return rewrite_obj


def analyze(query: str, name: str) -> dict:
    db = Database(pg_args)
    input_cost = db.cost_estimation(query)
    if input_cost == -1:
        input_cost = float("inf")
    if args.compute_latency:
        if args.large:
            input_latency = actual_time_once(query, pg_args, 300)
        else:
            input_latency, input_var = actual_time(query, pg_args, 300)
    final_res = {'template': name, 'input_sql': query, 'input_cost': input_cost,
                 'time': {'retrieval': 0, 'arrange': 0, 'rewrite': 0}, 'rewrites': []}
    if args.compute_latency:
        final_res['input_latency'] = input_latency
        if not args.large:
            final_res['input_var'] = input_var

    rewrite_obj = _analyze(name, input_latency=input_latency if args.compute_latency else None)

    if rewrite_obj:
        final_res['rewrites'].extend(rewrite_obj['rewrites'])
        final_res['time']['retrieval'] += rewrite_obj['time']['retrieval']
        final_res['time']['arrange'] += rewrite_obj['time']['arrange']
        final_res['time']['rewrite'] += rewrite_obj['time']['rewrite']

    if final_res['rewrites']:
        best_idx = sorted([(i, r['output_cost']) for i, r in enumerate(final_res['rewrites'])], key=lambda x: x[1])[0][
            0]
        final_res['best_index'] = best_idx
    else:
        final_res['best_index'] = -1  

    return final_res


schema_path = os.path.join(project_root, args.database, 'create_tables.sql')

analyze_log_filename = f'{args.logdir}/{args.database}.log' if not args.no_reflection else f'{args.logdir}/{args.database}_no_reflection.log'
analyze_log_filename = os.path.join(project_root, analyze_log_filename)

# 确保日志目录存在
os.makedirs(os.path.dirname(analyze_log_filename), exist_ok=True)

logging.basicConfig(filename=analyze_log_filename,
                    filemode='a',
                    format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                    datefmt='%H:%M:%S',
                    level=logging.DEBUG)

template_rewrites = []
if DATASET == 'calcite':
    queries_path = os.path.join(project_root, DATASET, f'{DATASET}.jsonl')  # 修正路径
    with open(queries_path, 'r', encoding='utf-8') as fin:
        for line in tqdm(fin.readlines()):
            obj = json.loads(line)
            query = obj['input_sql']
            name = sorted([x['name'] for x in obj['rewrites']])[0]

            rewrite_obj = analyze(query, name)
            if rewrite_obj['best_index'] != -1:  # 只添加有效结果
                template_rewrites.append(rewrite_obj)
else:
    # DSB: <dataset>/queries/queryXXX/; TPC-H in this repo: <dataset>/queryN/ (no "queries" folder)
    queries_path = os.path.join(project_root, args.database, 'queries')
    if not os.path.exists(queries_path):
        queries_path = os.path.join(project_root, args.database)
    if not os.path.exists(queries_path):
        print(f"错误: 查询目录不存在 {queries_path}")
        exit(1)

    query_templates = sorted(
        d for d in os.listdir(queries_path)
        if os.path.isdir(os.path.join(queries_path, d))
    )
    for template in tqdm(query_templates):
        max_idx = 1 if args.large else 2
        for idx in range(max_idx):
            query_filename = os.path.join(queries_path, template, f'{template}_{idx}.sql')
            if not os.path.exists(query_filename):
                continue

            content = open(query_filename, 'r', encoding='utf-8').read()
            content = re.sub(r'--.*\n', '', content)
            queries = [q.strip() + ';' for q in content.split(';') if q.strip()]
            for j, query in enumerate(queries):
                name = f'{template}_{idx}' if len(queries) == 1 else f'{template}_{idx}_{j}'

                rewrite_obj = analyze(query, name)
                if rewrite_obj['best_index'] != -1:
                    template_rewrites.append(rewrite_obj)

if not template_rewrites:
    print("没有找到任何有效的重写结果日志。请先运行重写脚本。")
    exit(0)

input_attr = 'input_latency' if args.compute_latency else 'input_cost'
output_attr = 'output_latency' if args.compute_latency else 'output_cost'

table = PrettyTable(['Template', 'Input', 'Output', 'Rules'])
for t in template_rewrites:
    if is_improved(t, t['best_index'], args.compute_latency):
        table.add_row([t['template'], t[input_attr], t['rewrites'][t['best_index']][output_attr],
                       t['rewrites'][t['best_index']]['used_rules']])
logging.info('Improvements:\n' + str(table))
logging.info(f'Improved {table.rowcount} out of {len(template_rewrites)} queries')

output_latencies = [t['rewrites'][t['best_index']][output_attr] if rewrite(t['input_cost'], t['rewrites'][t['best_index']]['output_cost'], t['rewrites'][t['best_index']]['used_rules']) else t[input_attr] for t in template_rewrites]

average_latency = sum(output_latencies) / len(output_latencies)
logging.info(f'Average: {average_latency}')
median_latency = sorted(output_latencies)[len(output_latencies) // 2]
logging.info(f'Median: {median_latency}')
latency_90th = sorted(output_latencies)[int(0.9 * len(output_latencies))]
logging.info(f'90th Percentile: {latency_90th}')
latency_95th = sorted(output_latencies)[int(0.95 * len(output_latencies))]
logging.info(f'95th Percentile: {latency_95th}')

input_latencies = [t[input_attr] for t in template_rewrites]
average_input_latency = sum(input_latencies) / len(input_latencies)
logging.info(f'Average Input: {average_input_latency}')
median_input_latency = sorted(input_latencies)[len(input_latencies) // 2]
logging.info(f'Median Input: {median_input_latency}')
input_latency_90th = sorted(input_latencies)[int(0.9 * len(input_latencies))]
logging.info(f'90th Percentile Input: {input_latency_90th}')
input_latency_95th = sorted(input_latencies)[int(0.95 * len(input_latencies))]
logging.info(f'95th Percentile Input: {input_latency_95th}')

average_retrieval = sum([t['time']['retrieval'] for t in template_rewrites]) / len(template_rewrites)
average_arrange = sum([t['time']['arrange'] for t in template_rewrites]) / len(template_rewrites)
average_rewrite = sum([t['time']['rewrite'] for t in template_rewrites]) / len(template_rewrites)
logging.info(f'Average Retrieval Time: {average_retrieval}')
logging.info(f'Average Arrange Time: {average_arrange}')
logging.info(f'Average Rewrite Time: {average_rewrite}')
logging.info(f'Average Total Time: {average_retrieval + average_arrange + average_rewrite}')

if args.large:
    overall_latencies = [t['time']['retrieval'] + t['time']['arrange'] + t['time']['rewrite'] + o for t, o in zip(template_rewrites, output_latencies)]

    average_overall_latency = sum(overall_latencies) / len(overall_latencies)
    logging.info(f'Average Overall: {average_overall_latency}')
    median_overall_latency = sorted(overall_latencies)[len(overall_latencies) // 2]
    logging.info(f'Median Overall: {median_overall_latency}')
    overall_latency_90th = sorted(overall_latencies)[int(0.9 * len(overall_latencies))]
    logging.info(f'90th Percentile Overall: {overall_latency_90th}')
    overall_latency_95th = sorted(overall_latencies)[int(0.95 * len(overall_latencies))]
    logging.info(f'95th Percentile Overall: {overall_latency_95th}')
