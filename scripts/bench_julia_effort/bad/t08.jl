function thomas(a,b,c,d)                               # BAD: pas de remontee
    n = length(b); cp = zeros(n-1); dp = zeros(n)
    cp[1] = c[1]/b[1]; dp[1] = d[1]/b[1]
    for i in 2:n-1
        m = b[i]-a[i-1]*cp[i-1]; cp[i] = c[i]/m; dp[i] = (d[i]-a[i-1]*dp[i-1])/m
    end
    dp[n] = (d[n]-a[n-1]*dp[n-1])/(b[n]-a[n-1]*cp[n-1])
    dp
end
