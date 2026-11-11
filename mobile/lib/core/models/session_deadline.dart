/// In-process wall-clock session. Ticks only repaint; background time counts.
/// This is intentionally not persisted across process death. Clock adjustments
/// can change progress, but never make it negative or exceed the target.
class SessionDeadline {
  SessionDeadline({required this.start, required this.duration}) {
    if (duration <= Duration.zero) {
      throw ArgumentError.value(duration, 'duration', 'Must be positive');
    }
  }

  final DateTime start;
  final Duration duration;
  DateTime get deadline => start.add(duration);

  int _elapsedMicros(DateTime now) =>
      now.difference(start).inMicroseconds.clamp(0, duration.inMicroseconds);

  double fraction(DateTime now) =>
      _elapsedMicros(now) / duration.inMicroseconds;

  int remainingSeconds(DateTime now) =>
      ((duration.inMicroseconds - _elapsedMicros(now)) /
              Duration.microsecondsPerSecond)
          .ceil();
}
