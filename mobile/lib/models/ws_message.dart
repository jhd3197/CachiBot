class WSEvent {
  const WSEvent({
    required this.type,
    required this.payload,
  });

  final String type;
  final Map<String, dynamic> payload;

  factory WSEvent.fromJson(Map<String, dynamic> json) {
    return WSEvent(
      type: json['type'] as String,
      payload: (json['payload'] as Map<String, dynamic>?) ?? {},
    );
  }

  Map<String, dynamic> toJson() => {
        'type': type,
        'payload': payload,
      };

  // Server → Client event types
  static const String thinking = 'thinking';
  static const String toolStart = 'tool_start';
  static const String toolEnd = 'tool_end';
  static const String message = 'message';
  static const String instructionDelta = 'instruction_delta';
  static const String usage = 'usage';
  static const String error = 'error';
  static const String done = 'done';
  static const String approvalNeeded = 'approval_needed';
  static const String modelFallback = 'model_fallback';

  // Client → Server event types
  static const String chat = 'chat';
  static const String cancel = 'cancel';
  static const String approval = 'approval';

  // Client-only synthetic events
  static const String reconnected = 'reconnected';
}

/// Approval request received from the server.
class ApprovalRequest {
  const ApprovalRequest({
    required this.id,
    required this.tool,
    required this.action,
    this.riskLevel = 'UNKNOWN',
    this.reasons = const [],
    this.code,
  });

  final String id;
  final String tool;
  final String action;
  final String riskLevel;
  final List<String> reasons;
  final String? code;

  factory ApprovalRequest.fromPayload(Map<String, dynamic> payload) {
    final details = (payload['details'] as Map<String, dynamic>?) ?? {};
    final rawReasons = details['reasons'];
    final reasons = rawReasons is List
        ? rawReasons.map((e) => e.toString()).toList()
        : <String>[];

    return ApprovalRequest(
      id: payload['id'] as String,
      tool: payload['tool'] as String,
      action: payload['action'] as String? ?? '',
      riskLevel: (details['riskLevel'] as String?) ?? 'UNKNOWN',
      reasons: reasons,
      code: details['code'] as String?,
    );
  }
}

class ToolCall {
  const ToolCall({
    required this.id,
    required this.tool,
    required this.args,
    this.result,
    this.success,
    required this.startTime,
    this.endTime,
  });

  final String id;
  final String tool;
  final Map<String, dynamic> args;
  final dynamic result;
  final bool? success;
  final DateTime startTime;
  final DateTime? endTime;

  bool get isRunning => endTime == null;

  ToolCall copyWith({
    dynamic result,
    bool? success,
    DateTime? endTime,
  }) {
    return ToolCall(
      id: id,
      tool: tool,
      args: args,
      result: result ?? this.result,
      success: success ?? this.success,
      startTime: startTime,
      endTime: endTime ?? this.endTime,
    );
  }
}
