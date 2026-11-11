import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:screentime_companion/core/models/companion.dart';
import 'package:screentime_companion/core/models/pet.dart';

/// Locks the Dart pet tables to the GLB bytes that actually ship.
///
/// Two failures this replaces with a machine check.  The first is the adult
/// `sleep` clip: its closing key was dropped in a rebuild, so the file held 125
/// frames while `pet.dart` still played a 4167 ms timer, and the loop snapped in
/// the app.  The second is the body export that lost its `skin` binding because a
/// tool removed the armature modifier and never restored it - every curve in the
/// file was still correct, so only a render could see a frozen body while the
/// eyelids moved.  Animation-curve audits cannot see either problem; these can.
///
/// Reads the assets from disk rather than through `rootBundle` so the test fails
/// with a real file path and stays a plain unit test.
class GlbFile {
  GlbFile._(this.path, this.json, this.bin);

  final String path;
  final Map<String, dynamic> json;
  final Uint8List bin;

  factory GlbFile.open(String assetPath) {
    final file = File(assetPath);
    expect(file.existsSync(), isTrue, reason: 'missing asset $assetPath');
    final bytes = file.readAsBytesSync();
    final header = ByteData.sublistView(bytes, 0, 20);
    expect(header.getUint32(0, Endian.little), 0x46546C67,
        reason: '$assetPath is not a GLB');
    var offset = 12;
    Map<String, dynamic>? json;
    Uint8List? bin;
    while (offset < bytes.length) {
      final chunk = ByteData.sublistView(bytes, offset, offset + 8);
      final length = chunk.getUint32(0, Endian.little);
      final type = chunk.getUint32(4, Endian.little);
      final body = offset + 8;
      if (type == 0x4E4F534A) {
        json = glbJson(
            String.fromCharCodes(bytes.sublist(body, body + length)));
      } else if (type == 0x004E4942) {
        bin = bytes.sublist(body, body + length);
      }
      offset = body + length + (length % 4 == 0 ? 0 : 4 - length % 4);
    }
    expect(json, isNotNull, reason: '$assetPath has no JSON chunk');
    expect(bin, isNotNull, reason: '$assetPath has no BIN chunk');
    return GlbFile._(assetPath, json!, bin!);
  }

  List<dynamic> get nodes => (json['nodes'] ?? const <dynamic>[]) as List;
  List<dynamic> get meshes => (json['meshes'] ?? const <dynamic>[]) as List;
  List<dynamic> get animations =>
      (json['animations'] ?? const <dynamic>[]) as List;

  /// Last keyframe time of every clip, straight out of the sampler inputs.
  Map<String, double> get clipSeconds {
    final out = <String, double>{};
    for (final anim in animations) {
      double last = 0;
      for (final sampler in (anim['samplers'] ?? const <dynamic>[]) as List) {
        final accessor = (json['accessors'] as List)[sampler['input']];
        final view = (json['bufferViews'] as List)[accessor['bufferView']];
        expect(accessor['componentType'], 5126,
            reason: 'time inputs are expected to be float32');
        expect(accessor['type'], 'SCALAR', reason: 'time inputs are scalars');
        final base = ((view['byteOffset'] ?? 0) as int) +
            ((accessor['byteOffset'] ?? 0) as int);
        final stride = (view['byteStride'] ?? 4) as int;
        final count = accessor['count'] as int;
        final data = ByteData.sublistView(
            bin, base, base + stride * (count - 1) + 4);
        for (var i = 0; i < count; i++) {
          final t = data.getFloat32(i * stride, Endian.little);
          if (t > last) last = t;
        }
      }
      out[(anim['name'] ?? '?') as String] = last;
    }
    return out;
  }

  /// Every mesh node with the answer to "will the GPU move this?" for it:
  /// skinned, or driven by node TRS animation.
  List<({String name, int vertices, bool skinned, bool driven, bool isBody})>
      get meshNodes {
    int vertexCount(dynamic mesh) {
      var total = 0;
      for (final prim
          in (mesh['primitives'] ?? const <dynamic>[]) as List) {
        final attributes = (prim['attributes'] ?? const <String, dynamic>{}) as Map;
        final position = attributes['POSITION'];
        if (position == null) continue;
        total += ((json['accessors'] as List)[position]['count'] as int);
      }
      return total;
    }
    final entries = <({int nodeIndex, Map node, dynamic mesh})>[];
    for (var i = 0; i < nodes.length; i++) {
      final node = nodes[i];
      if (node is Map && node.containsKey('mesh')) {
        entries.add((
          nodeIndex: i,
          node: node,
          mesh: meshes[node['mesh'] as int]
        ));
      }
    }
    if (entries.isEmpty) return const [];
    var bodyIndex = entries.first.nodeIndex;
    var biggest = -1;
    for (final e in entries) {
      final v = vertexCount(e.mesh);
      if (v > biggest) {
        biggest = v;
        bodyIndex = e.nodeIndex;
      }
    }
    final drivenNodes = <int>{};
    for (final anim in animations) {
      for (final channel in (anim['channels'] ?? const <dynamic>[]) as List) {
        final target = (channel['target'] as Map)['node'];
        if (target is int) drivenNodes.add(target);
      }
    }
    return [
      for (final e in entries)
        (
          name: (e.node['name'] ?? 'mesh:${e.mesh['name'] ?? '?'}') as String,
          vertices: vertexCount(e.mesh),
          skinned: _isSkinned(e.node, e.mesh),
          driven: drivenNodes.contains(e.nodeIndex),
          isBody: e.nodeIndex == bodyIndex,
        )
    ];
  }

  static bool _isSkinned(Map node, dynamic mesh) {
    if (!node.containsKey('skin')) return false;
    final primitives =
        ((mesh['primitives'] ?? const <dynamic>[]) as List).cast<Map>();
    if (primitives.isEmpty) return false;
    return primitives.every((p) {
      final attributes = (p['attributes'] ?? const <String, dynamic>{}) as Map;
      return attributes.containsKey('JOINTS_0') &&
          attributes.containsKey('WEIGHTS_0');
    });
  }
}

/// `json.decode` kept behind a helper so the failure names the asset.
Map<String, dynamic> glbJson(String source) {
  try {
    return Map<String, dynamic>.from(json.decode(source) as Map);
  } on FormatException {
    throw FormatException('GLB JSON chunk did not decode');
  }
}

void main() {
  const drakoAssets = ['drako_bayi', 'drako_remaja', 'drako_dewasa'];
  const allAssets = [
    'momo_bayi',
    'momo_remaja',
    'momo_dewasa',
    ...drakoAssets,
  ];

  group('delivered GLBs are bound to their skeleton', () {
    test('the body of every shipped companion mesh is skinned', () {
      for (final name in allAssets) {
        final glb = GlbFile.open('assets/3d/$name.glb');
        final meshes = glb.meshNodes;
        expect(meshes, isNotEmpty, reason: name);
        for (final mesh in meshes) {
          final movable = mesh.skinned || (mesh.driven && !mesh.isBody);
          expect(
            movable,
            isTrue,
            reason: '$name / ${mesh.name} (${mesh.vertices} verts) is neither '
                'skinned nor node-animated, so it cannot follow the rig',
          );
        }
        expect(meshes.where((m) => m.isBody && m.skinned), isNotEmpty,
            reason: '$name has no skinned body mesh');
      }
    });

    test('each Drako stage carries a skin with 26 joints and 25 clips', () {
      for (final name in drakoAssets) {
        final glb = GlbFile.open('assets/3d/$name.glb');
        expect(glb.json.containsKey('skins'), isTrue, reason: name);
        final skins = (glb.json['skins'] as List).cast<Map>();
        expect(skins, hasLength(1), reason: name);
        expect((skins.single['joints'] as List), hasLength(26), reason: name);
        expect(skins.single.containsKey('inverseBindMatrices'), isTrue,
            reason: name);
        expect(glb.animations, hasLength(25), reason: name);
      }
    });
  });

  group('pet.dart durations match the delivered clips', () {
    test('every Dart timer equals its clip length to the millisecond', () {
      // The tables are generated by rounding the clip's last keyframe time to
      // whole milliseconds, so the only legitimate slack is float32 storage
      // (~0.0001 ms).  A whole frame of slack was deliberately not allowed: the
      // adult `sleep` bug is exactly one frame (4167 ms in the file against a
      // 4200 ms timer) and a loose gate would have signed it off.
      const slack = Duration(milliseconds: 2);
      for (final family in PetFamily.values) {
        final profile = PetRegistry.of(family);
        for (final stage in Stage.values) {
          final asset = profile.look(stage).asset;
          final glb = GlbFile.open(asset);
          final clips = glb.clipSeconds;
          final table = profile.durations[stage]!;
          expect(
            table.keys.toSet(),
            clips.keys.toSet(),
            reason: '$asset: the Dart table and the file disagree on clip names',
          );
          for (final entry in table.entries) {
            final fileMs = (clips[entry.key]! * 1000).round();
            final drift = (entry.value.inMilliseconds - fileMs).abs();
            expect(
              drift <= slack.inMilliseconds,
              isTrue,
              reason: '$asset ${entry.key}: dart=${entry.value.inMilliseconds}ms '
                  'file=$fileMs ms '
                  '(off by ${drift}ms; regenerate the table with '
                  'tools/qa_rig/tmp_clip_durations.py --emit-dart)',
            );
          }
        }
      }
    });

    test('every clip the behaviour layer can pick exists in its GLB', () {
      for (final family in PetFamily.values) {
        final profile = PetRegistry.of(family);
        final picks = <String>[
          profile.sleepClip,
          profile.pettingClip,
          profile.celebrateClip,
          profile.greetClip,
          ...profile.tapClips,
          for (final mood in Mood.values) ...profile.idleClipsFor(mood),
        ];
        for (final stage in Stage.values) {
          final glb = GlbFile.open(profile.look(stage).asset);
          for (final clip in picks.toSet()) {
            expect(glb.clipSeconds.containsKey(clip), isTrue,
                reason: '${profile.look(stage).asset} is missing "$clip"');
          }
        }
      }
    });
  });
}
