"""Exercise cancellation and pipe stalls with a fake process, without inference."""
import json
from pathlib import Path
import queue
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from neural import DeadlineResultConsumed, KataGo


class FakeOutput:
    def __init__(self): self.lines = queue.Queue()
    def __iter__(self):
        while True:
            line = self.lines.get()
            if line is None: return
            yield line
    def emit(self, value): self.lines.put(json.dumps(value) + '\n')
    def close(self): pass


class FakeProcess:
    def __init__(self, finish_cancel=True, stall=False, reverse=False):
        self.stdout = FakeOutput()
        self.stdin = self
        self.sent = []
        self.finish_cancel = finish_cancel
        self.stall = stall
        self.release = threading.Event()
        self.killed = False
        self.reverse = reverse
        self.waited = False

    def write(self, line):
        query = json.loads(line)
        self.sent.append(query)
        if self.stall:
            self.release.wait()
            return
        if query.get('action') == 'terminate':
            if not self.reverse:
                self.stdout.emit(query)
            if self.finish_cancel:
                self.stdout.emit({'id': query['terminateId'], 'isDuringSearch': False, 'noResults': True})
            if self.reverse:
                self.stdout.emit(query)
        elif query['id'] == 'partial':
            self.stdout.emit({'id': 'partial', 'isDuringSearch': True, 'answer': 17})
        elif query['id'] != 'slow':
            self.stdout.emit({'id': query['id'], 'isDuringSearch': False, 'answer': 42})

    def flush(self): pass
    def close(self): self.stdout.lines.put(None)
    def wait(self, timeout=None):
        self.waited = True
        return 0
    def kill(self):
        self.killed = True
        self.release.set()
        self.stdout.lines.put(None)


class DeadlineTests(unittest.TestCase):
    def engine(self, directory, process):
        with patch('neural.subprocess.Popen', return_value=process):
            return KataGo(Path('fake'), Path('model'), Path('config'), Path(directory))

    def test_timeout_cancels_and_late_replies_do_not_poison_next_request(self):
        with tempfile.TemporaryDirectory() as directory:
            process = FakeProcess()
            with self.engine(directory, process) as kata:
                start = time.perf_counter()
                with self.assertRaises(TimeoutError):
                    kata.request({'id': 'slow', 'moves': []}, deadline=start + .03)
                self.assertLess(time.perf_counter() - start, .25)
                result = kata.request({'id': 'fresh', 'moves': []}, deadline=time.perf_counter() + 1)
                self.assertEqual(result['id'], 'fresh')
                self.assertEqual(kata.cancel_pending, set())
                self.assertEqual(kata.metrics['cancelled'], 1)
                self.assertEqual(kata.metrics['late_replies'], 2)
                self.assertEqual(process.sent[1]['terminateId'], 'slow')

    def test_cancel_ack_alone_never_allows_new_inference(self):
        with tempfile.TemporaryDirectory() as directory:
            process = FakeProcess(finish_cancel=False)
            with self.engine(directory, process) as kata:
                with self.assertRaises(TimeoutError):
                    kata.request({'id': 'slow', 'moves': []}, deadline=time.perf_counter() + .03)
                with self.assertRaises(TimeoutError):
                    kata.request({'id': 'too-early', 'moves': []}, deadline=time.perf_counter() + .03)
                self.assertNotIn('too-early', [r['id'] for r in process.sent])
                self.assertEqual(kata.cancel_pending, {'slow'})
                process.stdout.emit({'id': 'slow', 'isDuringSearch': False, 'noResults': True})
                result = kata.request({'id': 'fresh', 'moves': []}, deadline=time.perf_counter() + 1)
                self.assertEqual(result['answer'], 42)

    def test_expired_request_is_not_submitted(self):
        with tempfile.TemporaryDirectory() as directory:
            process = FakeProcess()
            with self.engine(directory, process) as kata:
                with self.assertRaises(TimeoutError):
                    kata.request({'id': 'expired'}, deadline=time.perf_counter() - 1)
                self.assertEqual(kata.metrics['sent'], 0)

    def test_stalled_pipe_cannot_hold_caller_and_owned_process_is_cleaned(self):
        with tempfile.TemporaryDirectory() as directory:
            process = FakeProcess(stall=True)
            with self.engine(directory, process) as kata:
                start = time.perf_counter()
                with self.assertRaises(TimeoutError):
                    kata.request({'id': 'slow', 'moves': []}, deadline=start + .03)
                self.assertLess(time.perf_counter() - start, .25)
            self.assertTrue(process.killed)
            self.assertFalse(kata.writer.is_alive())

    def test_reversed_cancel_response_order_is_drained(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.engine(directory, FakeProcess(reverse=True)) as kata:
                with self.assertRaises(TimeoutError):
                    kata.request({'id': 'slow', 'moves': []}, deadline=time.perf_counter() + .02)
                self.assertEqual(kata.request({'id': 'fresh'}, deadline=time.perf_counter()+1)['id'], 'fresh')
                self.assertFalse(kata.cancel_pending)

    def test_anytime_search_returns_only_predeadline_intermediate_then_drains(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.engine(directory, FakeProcess()) as kata:
                response = kata.request({'id': 'partial', 'moves': []},
                                        deadline=time.perf_counter()+.03, allow_partial=True)
                self.assertEqual(response['answer'], 17)
                self.assertTrue(response['_used_intermediate'])
                self.assertEqual(kata.metrics['cancelled'], 1)
                self.assertEqual(kata.request({'id': 'fresh'}, deadline=time.perf_counter()+1)['id'], 'fresh')

    def test_unexpected_response_poisons_instance_before_another_send(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.engine(directory, FakeProcess()) as kata:
                kata.lines.put(json.dumps({'id': 'slow', 'warning': 'changed settings'}))
                with self.assertRaisesRegex(RuntimeError, 'rejected or altered'):
                    kata.request({'id': 'slow', 'moves': []}, deadline=time.perf_counter()+1)
                sent = kata.metrics['sent']
                with self.assertRaisesRegex(RuntimeError, 'restart required'):
                    kata.request({'id': 'fresh'}, deadline=time.perf_counter()+1)
                self.assertEqual(kata.metrics['sent'], sent)

    def test_consumed_late_terminal_is_discarded_without_cancel(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.engine(directory, FakeProcess()) as kata:
                def late_response(deadline):
                    time.sleep(.03)
                    return {'id': 'slow', 'isDuringSearch': False}
                with patch.object(kata, '_receive', side_effect=late_response):
                    with self.assertRaises(DeadlineResultConsumed):
                        kata.request({'id': 'slow', 'moves': []}, deadline=time.perf_counter()+.02)
                self.assertFalse(kata.cancel_pending)
                self.assertEqual(kata.metrics['cancelled'], 0)

    def test_broken_pipe_during_close_still_reaps_process_and_closes_logs(self):
        with tempfile.TemporaryDirectory() as directory:
            process = FakeProcess()
            kata = self.engine(directory, process)
            def broken_close():
                process.stdout.lines.put(None)
                raise BrokenPipeError('buffered close')
            with patch.object(process, 'close', side_effect=broken_close):
                kata.close()
            self.assertTrue(process.waited)
            self.assertTrue(kata.wire.closed)
            self.assertTrue(kata.stderr.closed)


if __name__ == '__main__': unittest.main()
