DEFINE FUNCTION cosine_similarity($vec1: array<float>, $vec2: array<float>) {
    IF array::len($vec1) != array::len($vec2) {
        RETURN 0.0;
    };
    
    LET $dot_product = 0.0;
    LET $magnitude1 = 0.0;
    LET $magnitude2 = 0.0;
    
    FOR $i IN range::from(0, array::len($vec1)) {
        LET $v1 = $vec1[$i];
        LET $v2 = $vec2[$i];
        $dot_product += $v1 * $v2;
        $magnitude1 += $v1 * $v1;
        $magnitude2 += $v2 * $v2;
    };
    
    $magnitude1 = math::sqrt($magnitude1);
    $magnitude2 = math::sqrt($magnitude2);
    
    IF $magnitude1 == 0.0 OR $magnitude2 == 0.0 {
        RETURN 0.0;
    };
    
    RETURN $dot_product / ($magnitude1 * $magnitude2);
};