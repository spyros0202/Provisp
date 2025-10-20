%% Sheep Vital Data – Real Dataset Integration (TPS basis)
clc; clear; close all;
fprintf('--- START PIPELINE ---\n');

% ----------------------------
% 0) Folder with CSVs
% ----------------------------
dataDir = 'C:\Users\zenia\OneDrive\Υπολογιστής\provisp';
fprintf('[0] Data folder: %s\n', dataDir);

csvs = struct( ...
    'animals',     fullfile(dataDir,'animals.csv'), ...
    'devices',     fullfile(dataDir,'devices.csv'), ...
    'device_data', fullfile(dataDir,'device_data.csv'), ...
    'meteo',       fullfile(dataDir,'meteo_data.csv'), ...
    'farms',       fullfile(dataDir,'farms.csv'));

% ----------------------------
% 1) Load
% ----------------------------
fprintf('[1] Loading CSVs...\n');
T = struct();
if isfile(csvs.animals),     T.animals     = standardizeTable(readtable(csvs.animals));     else, T.animals = table(); end
if isfile(csvs.devices),     T.devices     = standardizeTable(readtable(csvs.devices));     else, T.devices = table(); end
if isfile(csvs.device_data), T.device_data = standardizeTable(readtable(csvs.device_data)); else, error('device_data.csv missing'); end
if isfile(csvs.meteo),       T.meteo       = standardizeTable(readtable(csvs.meteo));       else, T.meteo = table(); end
if isfile(csvs.farms),       T.farms       = standardizeTable(readtable(csvs.farms));       else, T.farms = table(); end
fprintf('   Tables loaded.\n');

% ----------------------------
% 2) Columns and derived features
% ----------------------------
fprintf('[2] Preparing columns...\n');
col.device_id = getcol_any(T, {'device_data','devices'}, {'id_api','device_id','deviceid'});
col.animal_id = getcol_any(T, {'devices','animals'}, {'id_animal','animal_id'});
col.farm_id   = getcol_any(T, {'animals','farms','meteo'}, {'farm_id','farm_id_api'});
col.timestamp = 'created';

% Compute movement magnitude from acc_x,y,z
if all(ismember({'acc_x','acc_y','acc_z'}, T.device_data.Properties.VariableNames))
    T.device_data.acc_mag = sqrt(T.device_data.acc_x.^2 + ...
                                 T.device_data.acc_y.^2 + ...
                                 T.device_data.acc_z.^2);
else
    T.device_data.acc_mag = zeros(height(T.device_data),1);
end
col.hr=''; col.temp='temperature'; col.move='acc_mag'; col.spd='';
fprintf('   Columns ready.\n');

% ----------------------------
% 3) Merge
% ----------------------------
fprintf('[3] Merging...\n');
M=T.device_data;
if ismember(col.timestamp,M.Properties.VariableNames), M.(col.timestamp)=toDatetimeSafe(M.(col.timestamp)); end
if ~isempty(T.devices)
    key_dev=intersectVars(M,T.devices,col.device_id);
    if ~isempty(key_dev), M=outerjoin(M,T.devices,'Keys',key_dev,'MergeKeys',true,'Type','left'); end
end
if ~isempty(T.animals)&&~isempty(col.animal_id)
    key_an=intersectVars(M,T.animals,col.animal_id);
    if ~isempty(key_an), M=outerjoin(M,T.animals,'Keys',key_an,'MergeKeys',true,'Type','left'); end
end
if ~isempty(T.farms)&&~isempty(col.farm_id)
    key_=intersectVars(M,T.farms,col.farm_id);
    if ~isempty(key_), M=outerjoin(M,T.farms,'Keys',key_,'MergeKeys',true,'Type','left'); end
end
fprintf('   Merge complete: %d rows\n',height(M));

% ----------------------------
% 4) Features
% ----------------------------
fprintf('[4] Building features...\n');
hr_col=zeros(height(M),1);
temp_col=toNumeric(M.(col.temp));
move_col=toNumeric(M.(col.move));
spd_col=zeros(height(M),1);
Xraw=[hr_col temp_col move_col spd_col];
valid=all(isfinite(Xraw),2);
Xraw=Xraw(valid,:);
ts=[];
if ismember(col.timestamp,M.Properties.VariableNames)
    ts=M.(col.timestamp); ts=ts(valid);
end
[X,~]=normalize_range(Xraw,-1,1);
fprintf('   %d samples x %d features\n',size(X,1),size(X,2));

% ----------------------------
% 5) Synthetic target
% ----------------------------
y=0.5*X(:,1)+0.2*X(:,2)+0.2*X(:,3)+0.1*X(:,4);

% ----------------------------
% 6) Split
% ----------------------------
N=size(X,1);
if ~isempty(ts)&&isdatetime(ts), [~,ord]=sort(ts); X=X(ord,:); y=y(ord); end
ntrain=max(1,round(0.7*N));
Xtr=X(1:ntrain,:); ytr=y(1:ntrain);
Xte=X(ntrain+1:end,:); yte=y(ntrain+1:end,:);
fprintf('[5] Train %d | Test %d\n',size(Xtr,1),size(Xte,1));

% ----------------------------
% 7) Hardware
% ----------------------------
V=3.3; I=0.08; P_mW=V*I*1000; runs=5;

% ----------------------------
% 8) proposed center selection function
% ----------------------------
fprintf('[6] proposed center selection function ...\n');
s=100; t=zeros(runs,1);
for r=1:runs
    tic;
    [~,centers]=proposed_center_selection_function(Xtr,s);
    Phi=tps_basis(Xtr,centers);                % TPS
    Phi=[Phi ones(size(Phi,1),1)];
    lambda=1e-6;
    W=(Phi'*Phi+lambda*eye(size(Phi,2)))\(Phi'*ytr);
    t(r)=toc;
end
T_=mean(t); E_=P_mW*T_*1e3/1000;
Phi_t=tps_basis(Xte,centers); Phi_t=[Phi_t ones(size(Phi_t,1),1)];
yp_=Phi_t*W; rmse_=sqrt(mean((yp_-yte).^2));
fprintf('   proposed center selection function %.2fs RMSE %.4f\n',T_,rmse_);

% ----------------------------
% 9) k-Means + TPS
% ----------------------------
fprintf('[7] k-Means + Thin Plate Spline (TPS)...\n');
C=100; t=zeros(runs,1);
for r=1:runs
    tic;
    [~,centersKM]=kmeans(Xtr,C,'MaxIter',300,'Replicates',3);
    Phi=tps_basis(Xtr,centersKM);                % TPS
    Phi=[Phi ones(size(Phi,1),1)];
    lambda=1e-6; Wkm=(Phi'*Phi+lambda*eye(size(Phi,2)))\(Phi'*ytr);
    t(r)=toc;
end
T_km=mean(t); E_km=P_mW*T_km*1e3/1000;
Phi_t=tps_basis(Xte,centersKM); Phi_t=[Phi_t ones(size(Phi_t,1),1)];
yp_km=Phi_t*Wkm; rmse_km=sqrt(mean((yp_km-yte).^2));
fprintf('   Done kM-TPS %.2fs RMSE %.4f\n',T_km,rmse_km);

% ----------------------------
% 10) MLP baseline
% ----------------------------
fprintf('[8] MLP baseline...\n');
t=zeros(runs,1);
hasNN=license('test','Neural_Network_Toolbox')||exist('feedforwardnet','file')==2;
if hasNN
    for r=1:runs
        tic;
        net=feedforwardnet([10 10]);
        net.trainParam.showWindow=false;
        net.trainParam.epochs=300;
        net=train(net,Xtr',ytr');
        t(r)=toc;
        fprintf('   Run %d %.2fs\n',r,t(r));
    end
    T_mlp=mean(t); E_mlp=P_mW*T_mlp*1e3/1000;
    yp_mlp=net(Xte')'; rmse_mlp=sqrt(mean((yp_mlp-yte).^2));
    fprintf('   Done MLP %.2fs RMSE %.4f\n',T_mlp,rmse_mlp);
else
    warning('NN Toolbox not available'); T_mlp=NaN; E_mlp=NaN; rmse_mlp=NaN;
end

% ----------------------------
% 11) Summary
% ----------------------------
fprintf('\n--- RESULTS ---\n');
fprintf('Algorithm           | Time (s) | Energy (mJ) | RMSE\n');
fprintf('----------------------------------------------------------\n');
fprintf('Proposed algorithm    | %.4f | %.3f | %.4f\n',T_,E_,rmse_);
fprintf('k-Means        | %.4f | %.3f | %.4f\n',T_km,E_km,rmse_km);
if ~isnan(T_mlp)
    fprintf('MLP (2x10)          | %.4f | %.3f | %.4f\n',T_mlp,E_mlp,rmse_mlp);
end
fprintf('-----------------------------\n');
fprintf('Pipeline complete.\n');

% =========================================================
% Helper functions
% =========================================================
function TT = standardizeTable(TT)
v = TT.Properties.VariableNames;
v = regexprep(v,'\s+','_'); v = lower(v);
TT.Properties.VariableNames = v;
end

function name = getcol(T,candidates)
if isempty(T), name=''; return; end
v=T.Properties.VariableNames; name='';
for i=1:numel(candidates)
    idx=strcmpi(v,lower(candidates{i}));
    if any(idx), name=v{find(idx,1)}; return; end
end
for i=1:numel(candidates)
    hit=find(contains(v,lower(candidates{i})),1);
    if ~isempty(hit), name=v{hit}; return; end
end
end

function name = getcol_any(Tstruct,table_order,candidates)
name='';
for i=1:numel(table_order)
    tname=table_order{i};
    if isfield(Tstruct,tname)&&~isempty(Tstruct.(tname))
        name=getcol(Tstruct.(tname),candidates);
        if ~isempty(name), return; end
    end
end
end

function keylist = intersectVars(A,B,key)
if isempty(key)||~ismember(key,A.Properties.VariableNames)||~ismember(key,B.Properties.VariableNames)
    keylist={};
else
    keylist={key};
end
end

function x = toNumeric(x)
if isnumeric(x), return; end
if islogical(x), x=double(x); return; end
if isstring(x)||ischar(x)||iscellstr(x)
    x=str2double(string(x));
else
    x=double(x);
end
end

function dt = toDatetimeSafe(v)
if isdatetime(v), dt=v; return; end
try
    dt=datetime(v,'InputFormat','yyyy-MM-dd''T''HH:mm:ss','TimeZone','UTC');
catch
    try, dt=datetime(v,'ConvertFrom','datenum','TimeZone','UTC');
    catch, dt=datetime(string(v),'TimeZone','UTC');
    end
end
end

function [Xn,scales] = normalize_range(X,a,b)
xmin=min(X,[],1); xmax=max(X,[],1);
rng=xmax-xmin; rng(rng==0)=1;
Xn=a+(X-xmin).*((b-a)./rng);
scales=struct('xmin',xmin,'xmax',xmax,'a',a,'b',b);
end

function Phi = tps_basis(X,centers)
% Thin Plate Spline basis: phi(r) = r^2 * log(r + eps)
K=size(X,1); L=size(centers,1);
Phi=zeros(K,L);
for i=1:K
    for j=1:L
        r=norm(X(i,:)-centers(j,:));
        if r==0
            Phi(i,j)=0;
        else
            Phi(i,j)=(r^2)*log(r+eps);
        end
    end
end
end

%---------------------------------------------------------------------
%
% function [L,U_centers] = proposed center selection function(U,s)     %
%                                                                      %
%           ask the authors for info                                   %
%                                                                      %
%---------------------------------------------------------------------
