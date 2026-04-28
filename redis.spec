# Redis spec file for Fedora

%global _hardened_build 1

# Tests can be enabled with --with tests
%bcond_with tests

Name:              redis
Version:           8.6.0
Release:           4%{?dist}
Summary:           A persistent key-value database

# License breakdown:
# - redis core: AGPL-3.0-only (tri-licensed: RSALv2/SSPLv1/AGPLv3, using AGPLv3)
# - deps/hiredis: BSD-3-Clause
# - deps/jemalloc, deps/linenoise, src/lzf*: BSD-2-Clause
# - deps/lua: MIT
# - deps/fpconv: BSL-1.0
# - deps/hdr_histogram: CC0-1.0 OR BSD-2-Clause
# - deps/xxhash: BSD-2-Clause
# - deps/fast_float: MIT
License:           AGPL-3.0-only AND BSD-3-Clause AND BSD-2-Clause AND MIT AND BSL-1.0
URL:               https://redis.io
Source0:           https://github.com/redis/redis/archive/%{version}/redis-%{version}.tar.gz
Source1:           %{name}.logrotate
Source2:           %{name}-sentinel.service
Source3:           %{name}.service
Source4:           %{name}.sysusers
Source5:           %{name}.tmpfiles
Source6:           %{name}.rpmlintrc

# Fix default paths in configuration files for RPM layout
Patch0:            %{name}-conf.patch

BuildRequires:     gcc
BuildRequires:     gcc-c++
BuildRequires:     make
BuildRequires:     systemd-devel
BuildRequires:     systemd-rpm-macros
BuildRequires:     pkgconfig(libsystemd)
BuildRequires:     openssl-devel >= 1.0.2
%if %{with tests}
BuildRequires:     procps-ng
BuildRequires:     tcl8
BuildRequires:     python3
%endif

Requires:          logrotate

# Bundled dependencies (built from source in deps/)
# from deps/jemalloc/VERSION
Provides:          bundled(jemalloc) = 5.3.0
# from deps/hiredis/hiredis.h
Provides:          bundled(hiredis) = 1.2.0
# from deps/lua/src/lua.h
Provides:          bundled(lua-libs) = 5.1.5
# from deps/linenoise/linenoise.h
Provides:          bundled(linenoise) = 1.0
# from src/lzf.h (no version)
Provides:          bundled(lzf)
# from deps/hdr_histogram/README.md
Provides:          bundled(hdr_histogram) = 0.11.0
# from deps/fast_float/README.md
Provides:          bundled(fast_float) = 6.1.4
# from deps/xxhash/xxhash.h
Provides:          bundled(xxhash) = 0.8.3
# from deps/fpconv (no version)
Provides:          bundled(fpconv)

# Module support infrastructure
%global redis_modules_abi 1
%global redis_modules_dir %{_libdir}/%{name}/modules
%global redis_modules_cfg %{_sysconfdir}/%{name}/modules
Provides:          redis(modules_abi)%{?_isa} = %{redis_modules_abi}

%description
Redis is an advanced key-value store. It is often referred to as a data
structure server since keys can contain strings, hashes, lists, sets and
sorted sets.

You can run atomic operations on these types, like appending to a string;
incrementing the value in a hash; pushing to a list; computing set
intersection, union and difference; or getting the member with highest
ranking in a sorted set.

In order to achieve its outstanding performance, Redis works with an
in-memory dataset. Depending on your use case, you can persist it either
by dumping the dataset to disk every once in a while, or by appending
each command to a log.

Redis also supports trivial-to-setup master-slave replication, with very
fast non-blocking first synchronization, auto-reconnection on net split
and so forth.

Other features include Transactions, Pub/Sub, Lua scripting, Keys with a
limited time-to-live, and configuration settings to make Redis behave like
a cache.

%package           devel
Summary:           Development header for Redis module development
Provides:          %{name}-static = %{version}-%{release}
Requires:          %{name}%{?_isa} = %{version}-%{release}

%description       devel
Header file required for building loadable Redis modules. Includes
redismodule.h and RPM macros for module packaging.


%prep
%autosetup -p1

mv deps/jemalloc/COPYING COPYING-jemalloc
mv deps/lua/COPYRIGHT             COPYRIGHT-lua
mv deps/hiredis/COPYING           COPYING-hiredis
mv deps/hdr_histogram/LICENSE.txt LICENSE-hdrhistogram
mv deps/hdr_histogram/COPYING.txt COPYING-hdrhistogram
mv deps/fpconv/LICENSE.txt        LICENSE-fpconv
mv deps/xxhash/LICENSE            LICENSE-xxhash

# Architecture-specific jemalloc tuning
# See https://bugzilla.redhat.com/2240293
%ifarch %ix86 %arm x86_64 s390x
sed -e 's/--with-lg-quantum/--with-lg-page=12 --with-lg-quantum/' -i deps/Makefile
%endif
%ifarch ppc64 ppc64le aarch64
sed -e 's/--with-lg-quantum/--with-lg-page=16 --with-lg-quantum/' -i deps/Makefile
%endif

# Module API version safety check
api=$(sed -n -e 's/#define REDISMODULE_APIVER_[0-9][0-9]* //p' src/redismodule.h)
if test "$api" != "%{redis_modules_abi}"; then
   : Error: Upstream API version is now ${api}, expecting %{redis_modules_abi}.
   : Update the redis_modules_abi macro and rebuild.
   exit 1
fi

# Generates macro file
cat << 'EOF' | tee macros.redis
%%redis_version     %{?upstream_intver}%{!?upstream_intver:%{upstream_ver}}
%%redis_modules_abi %redis_modules_abi
%%redis_modules_dir %redis_modules_dir
%%redis_modules_cfg %redis_modules_cfg
EOF

%global make_flags DEBUG="" V="echo" BUILD_WITH_SYSTEMD=yes BUILD_TLS=yes

%build
%make_build %{make_flags} PREFIX=%{_prefix}


%install
%make_install %{make_flags} PREFIX=%{buildroot}%{_prefix}

# System user
install -p -D -m 0644 %{S:4} %{buildroot}%{_sysusersdir}/%{name}.conf

# Install tmpfiles.d file
install -p -D -m 0644 %{S:5} %{buildroot}%{_tmpfilesdir}/%{name}.conf

# Filesystem.
install -d %{buildroot}%{_sharedstatedir}/%{name}
install -d %{buildroot}%{_localstatedir}/log/%{name}
install -d %{buildroot}%{redis_modules_dir}
install -d %{buildroot}%{_sysconfdir}/systemd/system/%{name}.service.d
install -d %{buildroot}%{_sysconfdir}/systemd/system/%{name}-sentinel.service.d

# Install logrotate configuration
install -pDm644 %{S:1} %{buildroot}%{_sysconfdir}/logrotate.d/%{name}

# Install configuration files
install -pDm640 %{name}.conf  %{buildroot}%{_sysconfdir}/%{name}/%{name}.conf
install -pDm640 sentinel.conf %{buildroot}%{_sysconfdir}/%{name}/sentinel.conf
install -dm750  %{buildroot}%{redis_modules_cfg}

# Install systemd unit files.
mkdir -p %{buildroot}%{_unitdir}
install -pm644 %{S:3} %{buildroot}%{_unitdir}
install -pm644 %{S:2} %{buildroot}%{_unitdir}

# Fix executable permissions
chmod 755 %{buildroot}%{_bindir}/%{name}-*

# Install redis module header for module development
install -pDm644 src/%{name}module.h %{buildroot}%{_includedir}/%{name}module.h

# Install RPM macros for redis modules
mkdir -p %{buildroot}%{_rpmmacrodir}
install -pDm644 macros.redis %{buildroot}%{_rpmmacrodir}/macros.%{name}


%check
%if %{with tests}
# https://github.com/redis/redis/issues/1417 (for "taskset -c 1")
taskset -c 1 make %{make_flags} test
make %{make_flags} test-sentinel
%endif

%post
%tmpfiles_create %{name}.conf

# Move /etc/redis/sentinel/sentinel.conf to /etc/redis
if [ -f %{_sysconfdir}/%{name}/sentinel/sentinel.conf ]; then
  if [ -f %{_sysconfdir}/%{name}/sentinel.conf.rpmnew ]; then
    rm %{_sysconfdir}/%{name}/sentinel.conf.rpmnew
  fi
  if ! cmp -s %{_sysconfdir}/%{name}/sentinel/sentinel.conf %{_sysconfdir}/%{name}/sentinel.conf; then
    mv %{_sysconfdir}/%{name}/sentinel.conf %{_sysconfdir}/%{name}/sentinel.conf.rpmnew
  fi
  mv %{_sysconfdir}/%{name}/sentinel/sentinel.conf %{_sysconfdir}/%{name}/sentinel.conf
fi

%systemd_post %{name}.service
%systemd_post %{name}-sentinel.service


%preun
%systemd_preun %{name}.service
%systemd_preun %{name}-sentinel.service


%postun
%systemd_postun_with_restart %{name}.service
%systemd_postun_with_restart %{name}-sentinel.service


%files
%license LICENSE.txt
%license COPYRIGHT-lua
%license COPYING-hiredis
%license LICENSE-hdrhistogram
%license COPYING-hdrhistogram
%license LICENSE-fpconv
%license LICENSE-xxhash
%license COPYING-jemalloc
%doc 00-RELEASENOTES
%doc README.md
%doc CONTRIBUTING.md
%doc MANIFESTO
%doc SECURITY.md

%config(noreplace) %{_sysconfdir}/logrotate.d/%{name}
%attr(0750, redis, root) %dir %{_sysconfdir}/%{name}
%attr(0750, redis, root) %dir %{redis_modules_cfg}
%attr(0640, redis, redis) %config(noreplace) %{_sysconfdir}/%{name}/%{name}.conf
%attr(0640, redis, redis) %config(noreplace) %{_sysconfdir}/%{name}/sentinel.conf

%dir %{_libdir}/%{name}
%dir %{redis_modules_dir}
%dir %attr(0750, redis, redis) %{_sharedstatedir}/%{name}
%dir %attr(0750, root, redis) %{_localstatedir}/log/%{name}
%attr(0640, redis, redis) %ghost %{_localstatedir}/log/%{name}/redis-server.log
%attr(0640, redis, redis) %ghost %{_localstatedir}/log/%{name}/redis-sentinel.log
%ghost %{_rundir}/%{name}

%{_bindir}/%{name}-server
%{_bindir}/%{name}-sentinel
%{_bindir}/%{name}-cli
%{_bindir}/%{name}-benchmark
%{_bindir}/%{name}-check-aof
%{_bindir}/%{name}-check-rdb

%{_unitdir}/%{name}.service
%{_unitdir}/%{name}-sentinel.service
%dir %{_sysconfdir}/systemd/system/%{name}.service.d
%dir %{_sysconfdir}/systemd/system/%{name}-sentinel.service.d

%{_sysusersdir}/%{name}.conf
%{_tmpfilesdir}/%{name}.conf

%exclude %{_rpmmacrodir}
%exclude %{_includedir}


%files devel
%license LICENSE.txt
%{_includedir}/%{name}module.h
%{_rpmmacrodir}/macros.%{name}


%changelog
* Tue Apr 28 2026 Daria Guy <daria.guy@redis.com> - 8.6.0-4
- Fix rpmlint errors: buildroot usage, tmpfiles creation, log dir permissions

* Tue Feb 17 2026 Daria Guy <daria.guy@redis.com> - 8.6.0-3
- Edit sentinel configuration file path in redis-sentinel service file
- Change %%post logic to create rpmnew only when needed

* Tue Feb 17 2026 Daria Guy <daria.guy@redis.com> - 8.6.0-2
- Added post section to handle /etc/redis/sentinel directory

* Wed Feb 11 2026 Daria Guy <daria.guy@redis.com> - 8.6.0-1
- Initial package for Redis 8.6.0
