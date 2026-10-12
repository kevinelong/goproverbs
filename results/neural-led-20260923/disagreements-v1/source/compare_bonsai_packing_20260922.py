"""Controlled Bonsai PTQ1 versus PQ2 packing comparison.

Default operation only prepares a protocol directory. Network access requires
``--download`` and inference requires ``--run``. This file does not import or
modify the September 20 runner or any historical result directory.
"""
import argparse
import contextlib
import ctypes
import hashlib
import http.client
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import urllib.parse
import urllib.request


LAB = Path('C:/Users/kevin/ai_bench')
HISTORICAL = LAB / 'round-20260920/bonsai'
RUNTIME = HISTORICAL / 'runtime/llama-server.exe'
RESULT_ROOT = LAB / 'packing-20260922'
MODEL_ROOT = RESULT_ROOT / 'models'
PTQ1 = MODEL_ROOT / 'bonsai-pinned-PTQ1.gguf'

HF_REVISION = '6ed5e12bf84b7a63069882c91dd9e9218647d17b'
PTQ1_BYTES = 5_946_648_928
PTQ1_SHA256 = '53107f530aa52eb00912263ab1ee29bd199261c87cd7b4ad4ca1318c1fe33ee3'
PQ2_SHA256 = '3907dc1658db1f78a9826bf8d5bcb8dc65db0d466388937af57f2294fae62ec1'
RUNTIME_ID = 'prism-b10709-9a9394a'
CONTEXTS = (8192, 32768)
SEED = 260922
REPETITIONS = 3
REQUEST_TIMEOUT = 120
PTQ1_URL = f'https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf/resolve/{HF_REVISION}/Ternary-Bonsai-2-27B-PTQ1_0.gguf'

FIXED_PROMPT = (
    'Write a Python function named merge_counts that combines two dictionaries '
    'of nonnegative integer counts. Return only the function in one code block.'
)


def sha256(path, block=8 * 1024 * 1024):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while True:
            chunk = stream.read(block)
            if not chunk:
                return value.hexdigest()
            value.update(chunk)


def file_identity(path):
    path = Path(path)
    return {'path': str(path.resolve()), 'bytes': path.stat().st_size,
            'sha256': sha256(path)}


def find_pq2(directory=HISTORICAL):
    matches = [path for path in Path(directory).rglob('*.gguf')
               if sha256(path) == PQ2_SHA256]
    if len(matches) != 1:
        raise RuntimeError(f'expected one pinned PQ2 model, found {len(matches)}')
    return matches[0]


def validate_ptq1(path=PTQ1):
    identity = file_identity(path)
    if identity['bytes'] != PTQ1_BYTES or identity['sha256'] != PTQ1_SHA256:
        raise RuntimeError('PTQ1 size or SHA256 differs from the pinned artifact')
    return identity


def validate_download_url(url):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname != 'huggingface.co':
        raise ValueError('PTQ1 URL must use https://huggingface.co')
    if f'/resolve/{HF_REVISION}/' not in parsed.path:
        raise ValueError('PTQ1 URL must pin the required Hugging Face revision')
    if 'ptq1' not in parsed.path.lower() or not parsed.path.lower().endswith('.gguf'):
        raise ValueError('PTQ1 URL must identify a PTQ1 GGUF file')


def download_ptq1(url, destination=PTQ1):
    """Download one explicitly identified file, then verify before publishing."""
    validate_download_url(url)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        return validate_ptq1(destination)
    partial = destination.with_suffix(destination.suffix + '.part')
    if partial.exists():
        raise FileExistsError(f'remove or inspect incomplete download: {partial}')
    request = urllib.request.Request(url, headers={'User-Agent': 'local-llm-lab/packing-20260922'})
    try:
        with urllib.request.urlopen(request, timeout=60) as response, partial.open('xb') as output:
            # HF redirects pinned objects to a content-addressed CDN URL.
            # The expected size and SHA256 below remain authoritative.
            length = response.headers.get('Content-Length')
            if length is not None and int(length) != PTQ1_BYTES:
                raise RuntimeError(f'PTQ1 HTTP size differs: {length}')
            while True:
                chunk = response.read(8 * 1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
        identity = validate_ptq1(partial)
        os.replace(partial, destination)
        identity['path'] = str(destination.resolve())
        return identity
    except BaseException:
        # Keep a partial file for diagnosis/resume decisions; never treat it as a model.
        raise


def reconstruct_sse(lines):
    text = ''
    terminal = False
    events = []
    calls = {}
    finishes = []
    for raw in lines:
        line = raw.decode('utf-8') if isinstance(raw, bytes) else raw
        line = line.strip()
        if not line or line.startswith(':'):
            continue
        if not line.startswith('data:'):
            raise ValueError(f'unexpected SSE line: {line!r}')
        payload = line[5:].strip()
        if payload == '[DONE]':
            terminal = True
            continue
        event = json.loads(payload)
        events.append(event)
        for choice in event.get('choices', []):
            text += choice.get('delta', {}).get('content') or ''
            if choice.get('finish_reason'):
                finishes.append(choice['finish_reason'])
            for call in choice.get('delta', {}).get('tool_calls', []):
                target = calls.setdefault(call.get('index', 0), {'name': '', 'arguments': ''})
                for key in target:
                    target[key] += call.get('function', {}).get(key) or ''
    if not terminal or not finishes:
        raise ValueError('SSE stream ended without [DONE] or finish reason')
    return {'text': text, 'events': events, 'done': terminal, 'calls': calls, 'finish_reasons': finishes}


def request_json(port, route, payload, timeout=None):
    timeout = REQUEST_TIMEOUT if timeout is None else timeout
    body = json.dumps(payload).encode('utf-8')
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=timeout)
    started = time.perf_counter()
    try:
        connection.request('POST', route, body=body,
                           headers={'Content-Type': 'application/json'})
        response = connection.getresponse()
        raw = response.read()
        elapsed = (time.perf_counter() - started) * 1000
        if response.status != 200:
            raise RuntimeError(f'HTTP {response.status}: {raw[:1000]!r}')
        return json.loads(raw), elapsed
    finally:
        connection.close()


def request_sse(port, payload, timeout=None, capture_path=None):
    timeout = REQUEST_TIMEOUT if timeout is None else timeout
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=timeout)
    started = time.perf_counter()
    try:
        connection.request('POST', '/v1/chat/completions',
                           body=json.dumps(payload).encode('utf-8'),
                           headers={'Content-Type': 'application/json'})
        response = connection.getresponse()
        if response.status != 200:
            raise RuntimeError(f'HTTP {response.status}: {response.read()[:1000]!r}')
        lines = []
        try:
            for line in iter(response.readline, b''):
                lines.append(line)
        finally:
            if capture_path is not None:
                Path(capture_path).write_bytes(b''.join(lines))
        rebuilt = reconstruct_sse(lines)
        return rebuilt, (time.perf_counter() - started) * 1000
    finally:
        connection.close()


def fixed_request(prompt=FIXED_PROMPT, stream=False):
    return {
        'model': 'pinned-local-bonsai',
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': 0,
        'seed': SEED,
        'max_tokens': 256,
        'stream': stream,
        'cache_prompt': False,
        'timings_per_token': True,
        'chat_template_kwargs': {'enable_thinking': False},
    }


def control_requests(port, folder=None):
    """Validate plain text, forced tool JSON, and streaming independently."""
    plain_request = fixed_request('Reply with exactly LOCAL_OK and nothing else.')
    plain, plain_ms = request_json(port, '/v1/chat/completions', plain_request)
    if folder:
        (folder / 'control-plain.json').write_text(json.dumps({'request': plain_request, 'response': plain, 'ms': plain_ms}, indent=2), encoding='ascii')
    content = plain['choices'][0]['message'].get('content')
    if not isinstance(content, str) or content.strip() != 'LOCAL_OK':
        raise RuntimeError('plain-text control did not return LOCAL_OK')

    tool_payload = fixed_request('Call emit_result with value 7. Do not answer in prose.')
    tool_payload['tools'] = [{'type': 'function', 'function': {
        'name': 'emit_result', 'description': 'Emit an integer result.',
        'parameters': {'type': 'object', 'properties': {'value': {'type': 'integer'}},
                       'required': ['value'], 'additionalProperties': False}}}]
    # This pinned Prism server parses tool_choice as a string. Object form is
    # silently downgraded to auto with a warning; one required tool is explicit.
    tool_payload['tool_choice'] = 'required'
    tool_payload['parallel_tool_calls'] = False
    tool, tool_ms = request_json(port, '/v1/chat/completions', tool_payload)
    if folder:
        (folder / 'control-tool.json').write_text(json.dumps({'request': tool_payload, 'response': tool, 'ms': tool_ms}, indent=2), encoding='ascii')
    calls = tool['choices'][0]['message'].get('tool_calls') or []
    if (tool['choices'][0].get('finish_reason') != 'tool_calls'
            or len(calls) != 1 or calls[0]['function']['name'] != 'emit_result'):
        raise RuntimeError('forced-tool control did not return emit_result')
    arguments = json.loads(calls[0]['function']['arguments'])
    if arguments != {'value': 7} or type(arguments.get('value')) is not int:
        raise RuntimeError(f'forced-tool arguments failed control: {arguments!r}')

    stream_payload = {**tool_payload, 'stream': True, 'stream_options': {'include_usage': True}}
    if folder:
        (folder / 'control-stream-request.json').write_text(json.dumps(stream_payload, indent=2), encoding='ascii')
    streamed, stream_ms = request_sse(port, stream_payload, capture_path=folder / 'control-stream.sse' if folder else None)
    stream_calls = list(streamed['calls'].values())
    stream_arguments = json.loads(stream_calls[0]['arguments']) if len(stream_calls) == 1 else None
    if (len(stream_calls) != 1 or stream_calls[0]['name'] != 'emit_result'
            or stream_arguments != {'value': 7} or type(stream_arguments.get('value')) is not int):
        raise RuntimeError('SSE tool control did not reconstruct expected arguments')
    return {'plain': {'request': plain_request, 'response': plain, 'ms': plain_ms},
            'tool': {'request': tool_payload, 'response': tool,
                     'arguments': arguments, 'ms': tool_ms},
            'stream': {'request': stream_payload, 'reconstructed': streamed,
                       'ms': stream_ms}}


def command_output(command, timeout=20):
    try:
        run = subprocess.run(command, capture_output=True, text=True, timeout=timeout,
                             creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        return {'command': command, 'exit_code': run.returncode,
                'stdout': run.stdout, 'stderr': run.stderr}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'command': command, 'error': repr(exc)}


def machine_state():
    result = {
        'gpu': command_output(['nvidia-smi', '--query-gpu=name,memory.used,memory.free,driver_version',
                               '--format=csv']),
        'compute_processes': command_output(['nvidia-smi', '--query-compute-apps=pid,process_name,used_memory',
                                             '--format=csv']),
        'ollama': command_output(['ollama', 'ps']),
    }
    class Memory(ctypes.Structure):
        _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)] + [
            (name, ctypes.c_ulonglong) for name in
            ('total', 'available', 'page_total', 'page_available', 'virtual_total',
             'virtual_available', 'extended')]
    try:
        memory = Memory()
        memory.length = ctypes.sizeof(memory)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
            result['ram_bytes'] = {'total': memory.total, 'available': memory.available}
    except (AttributeError, OSError):
        pass
    return result


def active_processes():
    script = ("$ErrorActionPreference = 'Stop'; Get-Process | Where-Object { "
              "$_.ProcessName -match '^(llama-server|llama-cli|katago)$' } | "
              "Select-Object Id,ProcessName | ConvertTo-Json -Compress")
    result = command_output(['powershell.exe', '-NoProfile', '-Command', script])
    if result.get('exit_code') != 0:
        raise RuntimeError(f'cannot inspect active model processes: {result}')
    text = result['stdout'].strip()
    return [] if not text else json.loads(text)


def preflight():
    locks = [LAB / 'round-20260920/RUNNING.lock', LAB / 'overnight-20260916/RUNNING.lock',
             LAB / 'continuation-20260922/RUNNING.lock', LAB / 'staging-20260922/RUNNING.lock']
    present = [str(path) for path in locks if path.exists()]
    if present:
        raise RuntimeError(f'active runner lock(s): {present}')
    processes = active_processes()
    if processes:
        raise RuntimeError(f'model process already active: {processes}')
    state = machine_state()
    if any(state[key].get('exit_code') != 0 for key in ('gpu', 'ollama')):
        raise RuntimeError('GPU or Ollama inspection failed')
    if len(state.get('ollama', {}).get('stdout', '').strip().splitlines()) > 1:
        raise RuntimeError('Ollama has a resident model')
    return state


def free_port():
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


@contextlib.contextmanager
def owned_server(command, log_path, startup_seconds=120):
    """Start and clean up only the exact child process created here."""
    with Path(log_path).open('w', encoding='utf-8') as log:
        proc = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                text=True,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            deadline = time.monotonic() + startup_seconds
            port = int(command[command.index('--port') + 1])
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    raise RuntimeError(f'owned server exited {proc.returncode}; see {log_path}')
                try:
                    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=1)
                    connection.request('GET', '/health')
                    response = connection.getresponse()
                    response.read()
                    connection.close()
                    if response.status == 200:
                        break
                except OSError:
                    time.sleep(0.25)
            else:
                raise TimeoutError(f'owned server startup exceeded {startup_seconds}s')
            yield proc
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=10)


def runtime_files(runtime):
    runtime = Path(runtime)
    files = [runtime] + sorted(runtime.parent.glob('*.dll'))
    return {str(path.resolve()): file_identity(path) for path in files}


def validate_runtime(runtime):
    result = command_output([str(runtime), '--version'])
    combined = result.get('stdout', '') + result.get('stderr', '')
    expected_tokens = ('10709', '9a9394a')
    if result.get('exit_code') != 0 or not all(token in combined for token in expected_tokens):
        raise RuntimeError(f'runtime version is not pinned {RUNTIME_ID}: {result}')
    return result


def run_case(args, packing, model, context, ngl):
    case_name = f'{packing}-ctx{context}-ngl{ngl}'
    case_dir = args.output / case_name
    case_dir.mkdir(exist_ok=False)
    port = free_port()
    command = [str(args.runtime), '-m', str(model), '-c', str(context), '-ngl', str(ngl),
               '--host', '127.0.0.1', '--port', str(port), '--seed', str(SEED),
               '--alias', 'pinned-local-bonsai', '-np', '1', '-b', '512', '-ub', '128',
               '-fa', 'on', '--fit', 'off', '--jinja', '--no-webui',
               '--chat-template-kwargs', '{"enable_thinking":false}', '--reasoning-budget', '0',
               '--temp', '0', '--top-k', '40', '--top-p', '0.95', '--repeat-penalty', '1',
               '-t', '16', '-tb', '16']
    if ngl == 0:
        command += ['--device', 'none', '--no-op-offload', '--no-kv-offload']
    record = {'packing': packing, 'context': context, 'ngl': ngl, 'command': command,
              'before': machine_state(), 'controls': None, 'warmup': None, 'repetitions': []}
    load_start = time.perf_counter()
    try:
        with owned_server(command, case_dir / 'server.log') as proc:
            record['pid'] = proc.pid
            record['load_ms'] = (time.perf_counter() - load_start) * 1000
            record['loaded'] = machine_state()
            record['controls'] = control_requests(port, case_dir)
            warmup_request = fixed_request('Reply with exactly: warm')
            warmup_response, warmup_ms = request_json(
                port, '/v1/chat/completions', warmup_request)
            record['warmup'] = {'request': warmup_request,
                                'response': warmup_response, 'ms': warmup_ms}
            for repetition in range(REPETITIONS):
                if (args.output / 'STOP').exists():
                    raise InterruptedError('packing STOP requested')
                response, elapsed = request_json(
                    port, '/v1/chat/completions', fixed_request())
                if not response['choices'][0]['message'].get('content') or not response.get('usage', {}).get('completion_tokens'):
                    raise RuntimeError('timed response lacks text or measured completion usage')
                record['repetitions'].append({'index': repetition, 'request': fixed_request(),
                                              'response': response, 'ms': elapsed,
                                              'state': machine_state()})
            record['placement_log'] = str((case_dir / 'server.log').resolve())
            record['status'] = 'complete'
    except BaseException as exc:
        record['status'] = 'failed'
        record['error'] = repr(exc)
        raise
    finally:
        record['after'] = machine_state()
        record['owned_server_exited'] = 'proc' not in locals() or proc.poll() is not None
        (case_dir / 'result.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    return record


def prepare(args):
    if not args.label or any(character not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for character in args.label):
        raise ValueError('label must contain only letters, digits, hyphen, and underscore')
    args.output = RESULT_ROOT / args.label
    args.output.mkdir(parents=True, exist_ok=False)
    protocol = {
        'status': 'prepared', 'created_unix': time.time(), 'label': args.label,
        'runtime_id': RUNTIME_ID, 'runtime': str(args.runtime.resolve()),
        'historical_inputs_read_only': str(HISTORICAL.resolve()),
        'ptq1': {'path': str(args.ptq1.resolve()), 'bytes': PTQ1_BYTES,
                  'sha256': PTQ1_SHA256, 'hf_revision': HF_REVISION},
        'pq2': {'sha256': PQ2_SHA256},
        'contexts': list(CONTEXTS), 'repetitions': REPETITIONS,
        'request_timeout_seconds': REQUEST_TIMEOUT,
        'seed': SEED, 'temperature': 0, 'thinking': False,
        'fixed_prompt': FIXED_PROMPT,
        'controls_before_timing': ['plain_text', 'forced_tool_json', 'sse_reconstruction'],
        'claims': 'Packing comparison only; no mathematical-equivalence claim.',
    }
    (args.output / 'protocol.json').write_text(json.dumps(protocol, indent=2), encoding='ascii')
    return protocol


def main():
    global REQUEST_TIMEOUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label', required=True)
    parser.add_argument('--download', action='store_true', help='explicitly download pinned PTQ1')
    parser.add_argument('--ptq1-url', default=PTQ1_URL, help='pinned Hugging Face resolve URL')
    parser.add_argument('--run', action='store_true', help='explicitly run inference after preflight')
    parser.add_argument('--cpu', action='store_true', help='add separate ctx8192/ngl0 cases')
    parser.add_argument('--request-timeout', type=int, choices=(120, 600), default=120,
                        help='Socket timeout; 600 is a separately labeled slow-CPU treatment')
    parser.add_argument('--only', action='append', choices=[
        f'{packing}-ctx{context}-ngl{ngl}' for packing in ('PTQ1', 'PQ2')
        for context, ngl in ((8192, 99), (32768, 99), (8192, 0))],
        help='Run only these cases from the fixed order; CPU selections require --cpu')
    parser.add_argument('--runtime', type=Path, default=RUNTIME)
    parser.add_argument('--ptq1', type=Path, default=PTQ1)
    args = parser.parse_args()
    REQUEST_TIMEOUT = args.request_timeout
    if args.download and not args.ptq1_url:
        parser.error('--download requires --ptq1-url')
    if args.cpu and not args.run:
        parser.error('--cpu requires --run')
    if args.only and (not args.run or (not args.cpu and any(case.endswith('ngl0') for case in args.only))):
        parser.error('--only requires --run, and CPU selections also require --cpu')
    protocol = prepare(args)
    protocol['harness'] = file_identity(Path(__file__))
    (args.output / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    lock_path = RESULT_ROOT / 'RUNNING.lock'
    owns_lock = False
    try:
        if args.download:
            protocol['downloaded_ptq1'] = download_ptq1(args.ptq1_url, args.ptq1)
        if not args.run:
            protocol['status'] = 'prepared'
            return
        if not args.runtime.is_file():
            raise FileNotFoundError(args.runtime)
        ptq1 = validate_ptq1(args.ptq1)
        pq2_path = find_pq2()
        pq2 = file_identity(pq2_path)
        protocol['inputs'] = {'runtime_version': validate_runtime(args.runtime),
                              'runtime_and_dlls': runtime_files(args.runtime),
                              'PTQ1': ptq1, 'PQ2': pq2}
        protocol['preflight'] = preflight()
        with lock_path.open('x', encoding='ascii') as lock:
            lock.write(json.dumps({'pid': os.getpid(), 'output': str(args.output)}))
        owns_lock = True
        protocol['status'] = 'running'
        protocol['cases'] = []
        order = [('PTQ1', args.ptq1, 8192, 99), ('PQ2', pq2_path, 8192, 99),
                 ('PQ2', pq2_path, 32768, 99), ('PTQ1', args.ptq1, 32768, 99)]
        if args.cpu:
            order += [('PTQ1', args.ptq1, 8192, 0), ('PQ2', pq2_path, 8192, 0)]
        if args.only:
            order = [case for case in order if f'{case[0]}-ctx{case[2]}-ngl{case[3]}' in args.only]
        protocol['run_order'] = [(p, c, n) for p, _, c, n in order]
        for packing, model, context, ngl in order:
            preflight()
            if (args.output / 'STOP').exists():
                raise InterruptedError('packing STOP requested')
            print('Packing case', packing, context, ngl, flush=True)
            protocol['cases'].append(run_case(args, packing, model, context, ngl))
            (args.output / 'protocol.json').write_text(json.dumps(protocol, indent=2), encoding='ascii')
        protocol['inputs_unchanged'] = (validate_ptq1(args.ptq1) == ptq1 and file_identity(pq2_path) == pq2
                                        and runtime_files(args.runtime) == protocol['inputs']['runtime_and_dlls'])
        if not protocol['inputs_unchanged']:
            raise RuntimeError('Pinned packing input changed during experiment')
        if file_identity(Path(__file__)) != protocol['harness']:
            raise RuntimeError('Packing harness changed during experiment')
        protocol['status'] = 'complete'
        protocol['after'] = machine_state()
        remaining = active_processes()
        resident = protocol['after'].get('ollama', {}).get('stdout', '').strip().splitlines()
        unloaded = not remaining and len(resident) <= 1
        protocol['model_unloaded_check'] = {
            'active_model_processes': remaining,
            'ollama_resident_rows': max(0, len(resident) - 1),
            'passed': unloaded,
        }
        if not unloaded:
            raise RuntimeError('model remains loaded after owned cleanup')
    except BaseException as exc:
        protocol['status'] = 'failed'
        protocol['error'] = repr(exc)
        raise
    finally:
        if owns_lock:
            lock_path.unlink()
        (args.output / 'protocol.json').write_text(json.dumps(protocol, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
