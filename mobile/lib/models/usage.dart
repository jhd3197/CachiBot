/// Usage statistics for a single agent response.
class UsageInfo {
  const UsageInfo({
    this.totalTokens = 0,
    this.promptTokens = 0,
    this.completionTokens = 0,
    this.totalCost = 0.0,
    this.iterations = 0,
    this.elapsedMs = 0.0,
    this.tokensPerSecond = 0.0,
    this.callCount = 0,
    this.errors = 0,
  });

  final int totalTokens;
  final int promptTokens;
  final int completionTokens;
  final double totalCost;
  final int iterations;
  final double elapsedMs;
  final double tokensPerSecond;
  final int callCount;
  final int errors;

  factory UsageInfo.fromJson(Map<String, dynamic> json) {
    return UsageInfo(
      totalTokens: (json['totalTokens'] as num?)?.toInt() ?? 0,
      promptTokens: (json['promptTokens'] as num?)?.toInt() ?? 0,
      completionTokens: (json['completionTokens'] as num?)?.toInt() ?? 0,
      totalCost: (json['totalCost'] as num?)?.toDouble() ?? 0.0,
      iterations: (json['iterations'] as num?)?.toInt() ?? 0,
      elapsedMs: (json['elapsedMs'] as num?)?.toDouble() ?? 0.0,
      tokensPerSecond: (json['tokensPerSecond'] as num?)?.toDouble() ?? 0.0,
      callCount: (json['callCount'] as num?)?.toInt() ?? 0,
      errors: (json['errors'] as num?)?.toInt() ?? 0,
    );
  }

  Map<String, dynamic> toJson() => {
        'totalTokens': totalTokens,
        'promptTokens': promptTokens,
        'completionTokens': completionTokens,
        'totalCost': totalCost,
        'iterations': iterations,
        'elapsedMs': elapsedMs,
        'tokensPerSecond': tokensPerSecond,
        'callCount': callCount,
        'errors': errors,
      };

  /// Human-readable elapsed time.
  String get formattedElapsed {
    if (elapsedMs < 1000) return '${elapsedMs.round()}ms';
    final seconds = elapsedMs / 1000;
    if (seconds < 60) return '${seconds.toStringAsFixed(1)}s';
    final minutes = seconds / 60;
    return '${minutes.toStringAsFixed(1)}min';
  }

  /// Human-readable cost string.
  String get formattedCost {
    if (totalCost < 0.01) return '<\$0.01';
    return '\$${totalCost.toStringAsFixed(2)}';
  }

  /// Human-readable token count with K/M suffixes.
  String get formattedTokens {
    if (totalTokens < 1000) return '$totalTokens';
    if (totalTokens < 1000000) return '${(totalTokens / 1000).toStringAsFixed(1)}K';
    return '${(totalTokens / 1000000).toStringAsFixed(1)}M';
  }
}
