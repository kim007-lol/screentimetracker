import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:screentime_companion/widgets/main_shell.dart';

void main() {
  testWidgets('tabs are lazy, retain form/scroll state, and mute inactive tickers',
      (tester) async {
    final visits = [0, 0, 0];
    var index = 1;
    late StateSetter select;
    final builders = List<WidgetBuilder>.generate(3, (i) => (_) {
      visits[i]++;
      return ListView(
        key: ValueKey('tab-$i'),
        children: [
          TextField(key: ValueKey('field-$i')),
          for (var row = 0; row < 40; row++)
            SizedBox(height: 60, child: Text('tab $i row $row')),
        ],
      );
    });
    await tester.pumpWidget(MaterialApp(
      home: StatefulBuilder(builder: (context, setState) {
        select = setState;
        return Scaffold(body: LazyTabStack(index: index, builders: builders));
      }),
    ));
    expect(visits, [0, 1, 0]);
    await tester.enterText(find.byKey(const ValueKey('field-1')), 'keep me');
    await tester.drag(find.byKey(const ValueKey('tab-1')), const Offset(0, -400));
    await tester.pumpAndSettle();
    final listScrollable = find
        .descendant(
          of: find.byKey(const ValueKey('tab-1')),
          matching: find.byType(Scrollable),
        )
        .first;
    final scroll = tester.state<ScrollableState>(listScrollable).position.pixels;
    select(() => index = 0);
    await tester.pump();
    expect(visits, [1, 1, 0]);
    final inactive = tester.element(find.byKey(
      const ValueKey('tab-1'), skipOffstage: false,
    ));
    expect(TickerMode.of(inactive), isFalse);
    expect(TickerMode.of(tester.element(find.byKey(const ValueKey('tab-0')))),
        isTrue);
    select(() => index = 1);
    await tester.pump();
    expect(visits, [1, 1, 0]);
    expect(tester.state<ScrollableState>(listScrollable).position.pixels, scroll);
    final field = tester.widget<EditableText>(find.byType(EditableText));
    expect(field.controller.text, 'keep me');
  });
}
