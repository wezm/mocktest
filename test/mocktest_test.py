import unittest
import re
import sys

import helper
import mocktest
from mocktest import mock_wrapper, raw_mock, pending, ignore, expect

def assert_desc(expr):
	assert expr, expr

class SomeError(RuntimeError):
	def __str__(self):
		return "args are %r" % (self.args,)
	

class TestAutoSpecVerification(unittest.TestCase):

	def setUp(self):
		mocktest._setup()
		self.stderr = mock_wrapper().named('stderr')
		sys.stderr = self.stderr.mock
		self.output = mock_wrapper(sys.stderr.write)
		print "all expectations is %r" % (mocktest.mock.MockWrapper._all_expectations,)
	
	def tearDown(self):
		print "all expectations is %r" % (mocktest.mock.MockWrapper._all_expectations,)
		mocktest._teardown()
	
	def run_suite(self, class_):
		mocktest._teardown()
		suite = unittest.makeSuite(class_)
		result = unittest.TestResult()
		suite.run(result)
		ret = result
		mocktest._setup()
		return result
	
	def run_method(self, test_func):
		class SingleTest(mocktest.TestCase):
			test_method = test_func
		
		result = self.run_suite(SingleTest)
		
		if not result.wasSuccessful():
			print "ERRORS: %s" % (result.errors,)
			print "FAILURES: %s" % (result.failures,)
		return result
		
	def test_should_hijack_setup_and_teardown(self):
		lines = []
		def capture(line):
			lines.append(line)
		backup_setup = mocktest._setup
		backup_teardown = mocktest._teardown
		
		mocktest.mock._setup = mock_wrapper().with_action(lambda: capture("_setup")).mock
		mocktest.mock._teardown = mock_wrapper().with_action(lambda: capture("_teardown")).mock
		
		class Foo(mocktest.TestCase):
			def setUp(self):
				print "SETUP"
				capture("setup")
			def tearDown(self):
				capture("teardown")
			def test_main_is_called(self):
				capture("main")

		result = self.run_suite(Foo)
		self.assertTrue(result.wasSuccessful())
		self.assertEqual(lines, ['_setup', 'setup', 'main', '_teardown', 'teardown'])
		
		mocktest.mock._setup = backup_setup
		mocktest.mock._teardown = backup_teardown
	
	def test_ignore(self):
		callback = raw_mock()
		mock_wrapper(callback).is_expected.exactly(0).times
			
		@ignore
		def test_failure(self):
			callback('a')
		
		self.assert_(self.run_method(test_failure).wasSuccessful())
		assert_desc(self.output.called.with_('[[[ IGNORED ]]] ... '))
	
	def test_should_ignore_with_description(self):
		callback = raw_mock()
		mock_wrapper(callback).is_expected.exactly(0).times
			
		@ignore('not done yet')
		def test_failure(self):
			callback('a')
		
		self.assert_(self.run_method(test_failure).wasSuccessful())
		assert_desc(self.output.called.with_('[[[ IGNORED ]]] (not done yet) ... '))
	
	def test_expectation_failures_do_not_cause_further_failures(self):
		class myTest(mocktest.TestCase):
			def test_a(self):
				foo = mocktest.mock_wrapper()
				foo.expects('blah').once()
			def test_b(self):
				pass
			def test_c(self):
				pass
		results = self.run_suite(myTest)
		self.assertEqual(3, results.testsRun)
		self.assertEqual(0, len(results.failures))
		self.assertEqual(1, len(results.errors))
		
	def test_pending(self):
		callback = raw_mock()
			
		@pending
		def test_failure(self):
			callback('a')
			raise RuntimeError, "something went wrong!"
		
		self.assert_(self.run_method(test_failure).wasSuccessful())
		assert_desc(self.output.called.with_('[[[ PENDING ]]] ... '))
		
		@pending("reason")
		def test_failure_with_reason(self):
			assert False
			callback('b')
		
		self.assert_(self.run_method(test_failure_with_reason).wasSuccessful())
		assert_desc(self.output.called.with_('[[[ PENDING ]]] (reason) ... '))
		
		@pending
		def test_successful_pending_test(self):
			assert True
			callback('c')
		
		self.assertEqual(self.run_method(test_successful_pending_test).wasSuccessful(), False)
		assert_desc(self.output.called.with_('test_successful_pending_test PASSED unexpectedly '))
		
		self.assertEqual(mock_wrapper(callback).called.exactly(2).times.get_calls(), [('a',), ('c',)])
	
	def test_invalid_usage_after_teardown(self):
		mocktest._teardown()
		
		e = None
		try:
			mock_wrapper()
		except Exception, e_:
			e = e_

		self.assertFalse(e is None, "no exception was raised")
		self.assertEqual(e.__class__, RuntimeError)
		self.assertEqual(e.message, "MockWrapper._setup has not been called. Make sure you are inheriting from mock.TestCase, not unittest.TestCase")
		mocktest._setup()


	def make_error(self, *args, **kwargs):
		print "runtime error is being raised..."
		raise SomeError(*args, **kwargs)
	
	def test_assert_equal_should_be_friendly_for_arrays(self):
		def arrayNE(s):
			s.assertEqual([1,2,3], [1,4,3])
			
		result = self.run_method(arrayNE)
		self.assertFalse(result.wasSuccessful())
		failmsgs = result.failures[0][1].split('\n')
		
		print "failmsgs = %s" % (failmsgs,)
		
		self.assertTrue('AssertionError: [1, 2, 3] != [1, 4, 3]' in failmsgs)
		self.assertTrue('lists differ at index 1:' in failmsgs)
		self.assertTrue('\t2 != 4' in failmsgs)

	def test_assert_equal_should_be_friendly_for_tuples(self):
		def arrayNE(s):
			s.assertEqual((1,2,3), (1,4,3))
			
		result = self.run_method(arrayNE)
		self.assertFalse(result.wasSuccessful())
		failmsgs = result.failures[0][1].split('\n')
		
		print "failmsgs = %s" % (failmsgs,)
		
		self.assertTrue('AssertionError: (1, 2, 3) != (1, 4, 3)' in failmsgs)
		self.assertTrue('lists differ at index 1:' in failmsgs)
		self.assertTrue('\t2 != 4' in failmsgs)

	def test_assert_equal_should_be_friendly_for_array_lengths(self):
		def arrayNE(s):
			s.assertEqual([1,2,3], [1])
			
		result = self.run_method(arrayNE)
		self.assertFalse(result.wasSuccessful())
		failmsgs = result.failures[0][1].split('\n')
		
		print "failmsgs = %s" % (failmsgs,)
		
		self.assertTrue('AssertionError: [1, 2, 3] != [1]' in failmsgs)
		self.assertTrue('lists differ at index 1:' in failmsgs)
		self.assertTrue('\t2 != (no more values)' in failmsgs)
			
	def test_assert_equal_should_work(self):
		def arrayEQ(s):
			s.assertEqual([1,2,3], [1,2,3])
			
		self.assertTrue(self.run_method(arrayEQ).wasSuccessful())
			
	def test_assert_equal_should_be_friendly_for_dict_key_diffs(self):
		def dictNE(s):
			s.assertEqual({'a': 'b'}, {'4': 'x', '5': 'd'})

		result = self.run_method(dictNE)
		self.assertFalse(result.wasSuccessful())
		failmsgs = result.failures[0][1].split('\n')
		
		print "failmsgs = %s" % (failmsgs,)
		
		self.assertTrue("AssertionError: %r != %r" % ({'a': 'b'}, {'4': 'x', '5': 'd'}) in failmsgs)
		self.assertTrue("dict keys differ: ['a'] != ['4', '5']" in failmsgs)

	def test_assert_equal_should_be_friendly_for_dict_value_diffs(self):
		def dictNE(s):
			s.assertEqual({'a': 'b', '4': 'x'}, {'4': 'x', 'a': 'd'})

		result = self.run_method(dictNE)
		self.assertFalse(result.wasSuccessful())
		failmsgs = result.failures[0][1].split('\n')
		
		print "failmsgs = %s" % (failmsgs,)
		
		self.assertTrue("AssertionError: %r != %r" % ({'a': 'b', '4': 'x'}, {'4': 'x', 'a': 'd'}) in failmsgs)
		self.assertTrue("difference between dicts: {'a': 'b'} vs {'a': 'd'}" in failmsgs)

	def test_assert_equal_should_use_super_if_desc_is_defined(self):
		def dictNE(s):
			s.assertEqual({'a': 'b', '4': 'x'}, {'4': 'x', 'a': 'd'}, 'foo went bad!')

		result = self.run_method(dictNE)
		self.assertFalse(result.wasSuccessful())
		failmsgs = result.failures[0][1].split('\n')
		
		print "failmsgs = %s" % (failmsgs,)
		self.assertTrue("AssertionError: foo went bad!" in failmsgs)
		
	def test_assert_equal_should_work(self):
		def dictEQ(s):
			s.assertEqual({'a':'1'}, {'a':'1'})
		self.assertTrue(self.run_method(dictEQ).wasSuccessful())



	def test_assert_raises_matches(self):
		def test_raise_match(s):
			s.assertRaises(RuntimeError, lambda: self.make_error(1,2), message="args are (1, 2)")
			s.assertRaises(Exception, self.make_error, matching="^a")
			s.assertRaises(Exception, self.make_error, matching="\\)$")
			s.assertRaises(RuntimeError, lambda: self.make_error('foo'), args=('foo',))
			s.assertRaises(RuntimeError, lambda: self.make_error(), args=())
		
		result = self.run_method(test_raise_match)
		self.assertTrue(result.wasSuccessful())
	
	def test_assert_true_fails_on_callables(self):
		def assert_truth(s):
			s.assertTrue(lambda x: True)
		result = self.run_method(assert_truth)
		self.assertFalse(result.wasSuccessful())

	def test_assert_false_fails_on_callables(self):
		def assert_falseth(s):
			s.assertFalse(lambda x: False)
		result = self.run_method(assert_falseth)
		self.assertFalse(result.wasSuccessful())

	def test_assert__fails_on_callables(self):
		def assert_assert_(s):
			s.assert_(lambda x: True)
		result = self.run_method(assert_assert_)
		self.assertFalse(result.wasSuccessful())
	
	def test_assert_raises_verifies_type(self):
		def test_raise_mismatch_type(s):
			s.assertRaises(TypeError, self.make_error)
		result = self.run_method(test_raise_mismatch_type)
		self.assertFalse(result.wasSuccessful())

	def test_assert_raises_verifies_message(self):
		def test_raise_mismatch_message(s):
			s.assertRaises(RuntimeError, self.make_error, message='nope')
		result = self.run_method(test_raise_mismatch_message)
		self.assertFalse(result.wasSuccessful())
	
	def test_assert_raises_verifies_regex(self):
		def test_raise_mismatch_regex(s):
			s.assertRaises(RuntimeError, self.make_error, matches='^a')
		result = self.run_method(test_raise_mismatch_regex)
		self.assertFalse(result.wasSuccessful())

	def test_expectation_formatting(self):
		self.assertEqual(
			repr(mock_wrapper().called.with_('foo', bar=1).twice()),
			'\n'.join([
				'Mock "unnamed mock" did not match expectations:',
				' expected exactly 2 calls with arguments equal to: \'foo\', bar=1',
				' received 0 calls'])
		)
	
	def test_expect_should_work_on_a_mock_or_wrapper(self):
		wrapper = mock_wrapper()
		mock = wrapper.mock
		
		expect(mock.a).once()
		wrapper.expects('b').once()
		wrapper.child('c').is_expected.once()

		self.assertTrue(len(mocktest.mockwrapper.MockWrapper._all_expectations) == 3)
		
		mock.a()
		mock.b()
		mock.c()


	def test_reality_formatting(self):
		m = mock_wrapper().named('ze_mock').mock
		m(1,2,3)
		m(foo='bar')
		m()
		m(1, foo=2)
		
		line_agnostic_repr = [
			re.sub('\.py:[0-9 ]{3} ', '.py:LINE ', line)
			for line in repr(mock_wrapper(m).called.once()).split('\n')]
		
		expected_lines = [
			'Mock "ze_mock" did not match expectations:',
			' expected exactly 1 calls',
			' received 4 calls with arguments:',
			'  1:   1, 2, 3                  // mocktest_test.py:LINE :: m(1,2,3)',
			"  2:   foo='bar'                // mocktest_test.py:LINE :: m(foo='bar')",
			'  3:   No arguments             // mocktest_test.py:LINE :: m()',
			'  4:   1, foo=2                 // mocktest_test.py:LINE :: m(1, foo=2)']
		
		for got, expected in zip(line_agnostic_repr, expected_lines):
			self.assertEqual(got, expected)

class MockTestTest(mocktest.TestCase):
	def test_should_do_expectations(self):
		f = mock_wrapper()
		f.expects('foo').once()
		f.mock.foo('a')
		f.mock.foo()
		self.assertRaises(AssertionError, mocktest._teardown, matching=re.compile('Mock "foo" .*expected exactly 1 calls.* received 2 calls.*', re.DOTALL))
		
		# pretend we're in a new test (wipe the expected calls register)
		mocktest.mock.MockWrapper._all_expectations = []

	def test_assert_raises_with_args(self):
		def func_with_args(arg1, arg2, extra):
			value = "%s: %d%s" % (arg1, arg2, extra)
			raise StandardError(value)

		self.assertRaises(StandardError, func_with_args, 'one', 2, extra='y', args=('one: 2y',))

if __name__ == '__main__':
	unittest.main()