import 'package:flutter_test/flutter_test.dart';
import 'package:screentime_companion/core/models/session_deadline.dart';

void main() {
  final start = DateTime(2026, 10, 28, 23, 59);
  test('deadline includes background time without requiring any ticks', () {
    final timer = SessionDeadline(
      start: start,
      duration: const Duration(minutes: 10),
    );
    expect(timer.remainingSeconds(start.add(const Duration(minutes: 4))), 360);
    expect(timer.fraction(start.add(const Duration(minutes: 4))), 0.4);
    expect(timer.remainingSeconds(start.add(const Duration(hours: 1))), 0);
    expect(timer.fraction(start.add(const Duration(hours: 1))), 1);
  });
  test('clock changes cannot produce negative or over-target elapsed time', () {
    final timer = SessionDeadline(
      start: start,
      duration: const Duration(seconds: 30),
    );
    expect(timer.remainingSeconds(start.subtract(const Duration(days: 1))), 30);
    expect(timer.fraction(start.subtract(const Duration(days: 1))), 0);
    expect(timer.fraction(start.add(const Duration(days: 1))), 1);
    expect(
      timer.remainingSeconds(start.add(const Duration(milliseconds: 500))),
      30,
    );
  });
  test('nonpositive durations are rejected', () {
    expect(
      () => SessionDeadline(start: start, duration: Duration.zero),
      throwsArgumentError,
    );
  });
}
