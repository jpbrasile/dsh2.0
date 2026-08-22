function thomas(a::AbstractVector, b::AbstractVector, c::AbstractVector, d::AbstractVector)
    n = length(b)
    cp = similar(float(c), n-1); dp = similar(float(d), n)
    cp[1] = c[1] / b[1]; dp[1] = d[1] / b[1]
    for i in 2:n-1
        m = b[i] - a[i-1]*cp[i-1]
        cp[i] = c[i] / m
        dp[i] = (d[i] - a[i-1]*dp[i-1]) / m
    end
    dp[n] = (d[n] - a[n-1]*dp[n-1]) / (b[n] - a[n-1]*cp[n-1])
    x = similar(dp)
    x[n] = dp[n]
    for i in n-1:-1:1; x[i] = dp[i] - cp[i]*x[i+1]; end
    x
end
